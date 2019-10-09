#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# A short script to that wraps the Persephone phoneme recognition system to
# act as a local recognizer in ELAN.
#

import atexit
import os
import os.path
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

import persephone.corpus
import persephone.corpus_reader
import persephone.experiment
import persephone.preprocess.feat_extract
import persephone.rnn_ctc

import pydub


# The set of annotations (dicts) parsed out of the given ELAN tier.
annotations = []

# The parameters provided by the user via the ELAN recognizer interface
# (specified in CMDI).
params = {}

# The parameters that were originally used to load the training corpus and
# train the Persephone model being used for transcription here.
model_parameters = {}


@atexit.register
def cleanup():
    # When this recognizer ends (whether by finishing successfully or when
    # cancelled), run through all of the available annotations and remove
    # each temporary audio clip, its corresponding '.npy' feature file, and
    # all associated symlinks.
    for annotation in annotations:
        if 'wav_symlink' in annotation:
            os.unlink(annotation['wav_symlink'])
            del(annotation['wav_symlink'])

        if 'feat_symlink' in annotation:
            os.unlink(annotation['feat_symlink'])
            del(annotation['feat_symlink'])

        if 'clip' in annotation:
            annotation['clip'].close()
            del(annotation['clip'])

        if 'npy_symlink' in annotation:
            os.unlink(annotation['npy_symlink'])
            del(annotation['npy_symlink'])

        if 'npy' in annotation:
            os.remove(annotation['npy'])
            del(annotation['npy'])

    # Remove 'untranscribed_prefixes.txt' if it exists.
    if params.get('corpus_dir', None) and \
       os.path.exists(os.path.join(params['corpus_dir'], \
                      'untranscribed_prefixes.txt')):
        os.remove(os.path.join(params['corpus_dir'], \
                  'untranscribed_prefixes.txt'))

    # All other temporary files and directories created by 'tempfile' methods
    # will be removed automatically.

def to_tsuutina_orth(s):
    """ Convert Persephone phoneme strings to Tsuut'ina orthographic forms. """
    # Remove utterance-initial glottal stops (not part of the current
    # orthography).
    s = re.sub(r'^ʔ', '', s)

    # Turn two-vowel sequences with contour tones ("aa HM") into simpler
    # sequences of vowels followed by tones ("a H a M")
    s = re.sub(r'([aiouAIOU])([aiouAIOU]) ([LMH])([LMH])', '\\1 \\3 \\2 \\4', s)

    # Turn long vowels with level tones ("aa H") into simpler sequences of
    # vowels followe by tones  ("a H a H")
    s = re.sub(r'([aiouAIOU])([aiouAIOU]) ([LMH])( |$)', \
        '\\1 \\3 \\2 \\3\\4', s)

    # Temporarily turn tone markers into combining diacritics.
    s = s.replace(' H', u'\u0301')
    s = s.replace(' M', '')
    s = s.replace(' L', u'\u0300')

    # Remove all spaces between phonemes.
    s = s.replace(' ', '')

    # Turn vowel-plus-combining-accent combinations into single, composed
    # characters.
    s = unicodedata.normalize('NFC', s)
    return s

def to_sauk_orth_separate(s):
    """ Convert Persephone phoneme strings from vowel plus length to regular
        Sauk orthographic forms (where circumflexes mark vowel length."""

    # Remove short vowel markers altogether.
    s = s.replace(' S', '')

    # Turn long vowel markers into combining circumflexes, then make sure
    # we never end up with more than one circumflex in a row.
    s = re.sub(' L', u'\N{COMBINING CIRCUMFLEX ACCENT}', s)
    s = re.sub('\N{COMBINING CIRCUMFLEX ACCENT}+', \
        '\N{COMBINING CIRCUMFLEX ACCENT}', s)

    return to_sauk_orth_integrated(s)

def to_sauk_orth_integrated(s):
    """ Convert Persephone phoneme strings that use circumflex accents to mark
        vowel length back into the regular Sauk orthogrphy. """

    # Remove all spaces between phonemes.
    s = s.replace(' ', '')

    # Re-expand filled pauses and interjections.
    s = s.replace('UHHUH', ' uh-huh, ')
    s = s.replace('MHM', ' mhm, ')
    s = s.replace('UH', ' uh, ')
    s = s.replace('UM', ' um, ')

    # Turn vowel-plus-combining-accent combinations into single, composed
    # characters.
    s = unicodedata.normalize('NFC', s)
    return s.strip()


# Begin by tracking down the ffmpeg(1) executable that this recognizer will use
# to process audio materials.  If ffmpeg(1) doesn't exist in the current path, 
# exit now to save everyone some heartbreak later on.
ffmpeg = shutil.which('ffmpeg')
if not ffmpeg:
    sys.exit(-1)

# Read in all of the parameters that ELAN passes to this local recognizer on
# standard input.
for line in sys.stdin:
    match = re.search(r'<param name="(.*?)".*?>(.*?)</param>', line)
    if match:
        params[match.group(1)] = match.group(2).strip()

# Prepare to convert Persephone phoneme strings back into the given community
# orthography, if requested.
#
# TODO: Fix this to look at the label type (e.g., 'phonemes_len_separate'),
# then automatically choose the right orthographic conversion routine. That
# should let us keep the language list to language names only. FIXME
to_orth = None
if 'orthography' in params:
    if params['orthography'] == 'Tsuut&apos;ina':
        to_orth = to_tsuutina_orth
    elif params['orthography'] == 'Sauk-Separate':
        to_orth = to_sauk_orth_separate
    elif params['orthography'] == 'Sauk-Circumflex':
        to_orth = to_sauk_orth_integrated

# Read in the parameters that were originally used to read the training corpus
# and configure the model that will be used for transcription here.
with open(os.path.join(params['exp_dir'], 'model_description.txt'), 'r', \
     encoding = 'utf-8') as f:
    for line in f:
        match = re.search(\
            r'(num_train|batch_size|num_layers|hidden_size)=(\d+)', line)
        if match:
            model_parameters[match.group(1)] = int(match.group(2))


# With those parameters in hand, grab the 'input_tier' parameter, open that
# XML document, and read in all of the annotation start times, end times,
# and values.
print("PROGRESS: 0.1 Loading annotations on input tier")
with open(params['input_tier'], 'r', encoding = 'utf-8') as input_tier:
    for line in input_tier:
        match = re.search(r'<span start="(.*?)" end="(.*?)"><v>(.*?)</v>', line)
        if match:
            annotation = { \
                'start': int(float(match.group(1)) * 1000.0), \
                'end' : int(float(match.group(2)) * 1000.0), \
                'value' : match.group(3) }
            annotations.append(annotation)

# Then use ffmpeg(1) to convert the 'source' audio file into a temporary 16-bit
# mono 16KHz WAV, then load that temp file into pydub for easier exporting of
# audio clips in the format that Persephone expects. 
print("PROGRESS: 0.2 Converting source audio")
converted_audio_file = tempfile.NamedTemporaryFile(suffix = '.wav')
subprocess.call([ffmpeg, '-y', '-v', '0', \
    '-i', params['source'], \
    '-ac', '1',
    '-ar', '16000',
    '-sample_fmt', 's16',
    '-acodec', 'pcm_s16le', \
    converted_audio_file.name])
converted_audio = pydub.AudioSegment.from_file(converted_audio_file, \
    format = 'wav')

# Create a directory for untranscribed features in 'feat' if needed.
untranscribed_dir = os.path.join(params['corpus_dir'], 'feat', 'untranscribed')
if not os.path.exists(untranscribed_dir):
    os.mkdir(untranscribed_dir)

# Create a set of WAV clips for each of the annotations specified in
# 'input_tier' in the format that Persephone expects, storing them under
# temporary names in the 'wav' directory under the given corpus data
# directory and making a list of their names (without the file extensions)
# in 'untranscribed_prefixes.txt'.
#
# (When we reload the existing training corpus with these temporary audio
#  clips saved in 'wav', Persephone will copy (and convert, if needed) each
#  clip to 'feat', creating the necessary '.npy' files along the way.  We
#  still need to create 'untranscribed_prefixes.txt' by hand (and, later, move
#  the new clips and .npy files into 'feat/untranscribed/', while keeping
#  copies in 'wav' at least until we've reloaded the corpus -- Persephone
#  won't recognize them as untranscribed unless they're in both 'wav' *and*
#  'feat/untranscribed'), but that's not  hard to do.
print("PROGRESS: 0.3 Creating temporary clips")
prefix_to_annotation = {}
with open(os.path.join(params['corpus_dir'], 'untranscribed_prefixes.txt'), \
          'w', encoding = 'utf-8') as untranscribed_prefixes:
    for annotation in annotations:
        # Save the audio clip in a named temporary file in the corpus 'feat/
        # untranscribed' directory. 
        annotation['clip'] = tempfile.NamedTemporaryFile(suffix = '.wav', \
            dir = untranscribed_dir)
        clip = converted_audio[annotation['start']:annotation['end']]
        clip.export(annotation['clip'], format = 'wav')

        # Add an entry for this temporary clip's file name to 
        # 'untranscribed_prefixes.txt'.
        annotation['clip_name'] = os.path.basename(annotation['clip'].name)
        annotation['clip_prefix'] = \
            os.path.splitext(annotation['clip_name'])[0]
        print(annotation['clip_prefix'], file = untranscribed_prefixes)

        # Make a symlink to this clip in the 'wav' directory. (Persephone
        # requires that the WAV files live in both locations)
        annotation['wav_symlink'] = os.path.join(params['corpus_dir'], \
            'wav', annotation['clip_name'])
        os.symlink(annotation['clip'].name, annotation['wav_symlink'])

        # Map from this prefix to the corresponding annotation (for quick
        # lookups later on when parsing out recognized text)
        prefix_to_annotation[annotation['clip_prefix']] = annotation

# Now that clips in the appropriate format have been created, close (and
# thereby delete) the temporary converted source recording.  This isn't
# strictly necessary, but it doesn't hurt.
converted_audio_file.close()

# Now prepare input features for all of the clips in 'feat/untranscribed'.
# Having these features in place before loading the corpus convinces
# Persephone that it doesn't need to reprocess the entire corpus, lowering
# the overall time required for transcription.
print("PROGRESS: 0.4 Extracting features from clips")
persephone.preprocess.feat_extract.from_dir(untranscribed_dir, \
    params['feat_type'])

# If needed, make symlinks to both the clip *and* the corresponding input
# feature ('.npy') in the 'feat' directory, as well.
print("PROGRESS: 0.5 Creating temporary symlinks to clips and features")
for annotation in annotations:
    annotation['feat_symlink'] = os.path.join(params['corpus_dir'], \
        'feat', annotation['clip_name'])
    os.symlink(annotation['clip'].name, annotation['feat_symlink'])

    feat_fname = '%s.%s.npy' % (annotation['clip_prefix'], params['feat_type'])

    annotation['npy'] = os.path.join(untranscribed_dir, feat_fname)
    annotation['npy_symlink'] = os.path.join(params['corpus_dir'], 'feat', \
        feat_fname)
    os.symlink(annotation['npy'], annotation['npy_symlink'])

# Now that all of the clips and '.npy' files are where they need to be for
# Persephone to find them and an 'untranscribed_prefixes.txt' file is in place,
# load the corpus.  Persephone should now find all of these files and know to
# treat them as untranscribed segments.
print("PROGRESS: 0.6 Loading corpus into Persephone")
corp = persephone.corpus.Corpus(feat_type = params['feat_type'], \
    label_type = params['label_type'], tgt_dir = params['corpus_dir'])

# Then load the Persephone model specified in the 'persephone_model' parameter,
# then use it to start transcribing the clips created above (ideally reporting
# our progress via messages on stdout, though that doesn't look to be possible
# here with the current API.  Sigh...)
print("PROGRESS: 0.7 Creating temporary experiment directory")
temp_dir = tempfile.TemporaryDirectory()
new_experiment_dir = persephone.experiment.prep_exp_dir(temp_dir.name)

print("PROGRESS: 0.8 Creating Persephone model")
corp_reader = persephone.corpus_reader.CorpusReader(corp, \
    num_train = model_parameters['num_train'], \
    batch_size = model_parameters['batch_size'])

model = persephone.rnn_ctc.Model(new_experiment_dir, corp_reader, \
    num_layers = model_parameters['num_layers'], \
    hidden_size = model_parameters['hidden_size'])

# 'exp_dir' (e.g., '5') - experiment dir of trained model to apply
# /Users/chris/Desktop/CURRENT-PROJECTS/Persephone/persephone-tutorial/exp/5
print("PROGRESS: 0.9 Transcribing clips")
model.transcribe(os.path.join(params['exp_dir'], 'model', 'model_best.ckpt'))

# Now that transcription is finished, we can open 'EXPERIMENT_DIR/
# transcriptions/hyps.txt' and parse out the phoneme strings, storing them
# under the corresponding annotation.
with open(os.path.join(new_experiment_dir, 'transcriptions', 'hyps.txt'), \
    'r', encoding = 'utf-8') as recognized_text_file:
    while True:
        # Read the file in three-line blocks.
        prefix = recognized_text_file.readline()
        if not prefix:
            break

        # Strip off the path and '.{FEAT}.npy' file extensions to get back
        # to a usable prefix.
        prefix = os.path.basename(prefix)
        prefix = prefix[:prefix.index('.')]

        text = recognized_text_file.readline()
        recognized_text_file.readline()  # skip empty third line

        # Find the corresponding annotation and stores the recognized text
        # in it under 'value'.
        annotation = prefix_to_annotation[prefix]
        annotation['value'] = text.strip()

# Then open 'output_tier' for writing, and return all of the new phoneme
# strings produced by Persephone as the contents of <span> elements (see
# below).
print("PROGRESS: 0.95 Preparing output tier")
with open(params['output_tier'], 'w', encoding = 'utf-8') as output_tier:
    # Write document header.
    output_tier.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    output_tier.write('<TIER xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="file:avatech-tier.xsd" columns="PersephoneOutput">\n')

    # Write out annotations and recognized text (e.g., '<span start="17.492"
    # end="18.492"><v>OUTPUT</v></span>').  If we've been asked to, convert
    # from Persephone's phoneme strings back into the given language's
    # orthography.
    if to_orth:
        for annotation in annotations:
            output_tier.write(\
                '    <span start="%s" end="%s"><v>%s</v></span>\n' %\
                (annotation['start'], annotation['end'], \
                 to_orth(annotation['value'])))
    else:
        for annotation in annotations:
            output_tier.write(\
                '    <span start="%s" end="%s"><v>%s</v></span>\n' %\
                (annotation['start'], annotation['end'], annotation['value']))

    output_tier.write('</TIER>\n')

# Finally, tell ELAN that we're done.
print('RESULT: DONE.')
