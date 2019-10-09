Persephone-ELAN v0.1.1
======================

Persephone-ELAN integrates the automatic phoneme recognition methods offered by
`Persephone <https://github.com/persephone-tools/persephone>`_ (`Adams et al.
2018 <https://www.aclweb.org/anthology/L18-1530/>`_, `Michaud et al. 2018 
<http://hdl.handle.net/10125/24793>`_) into `ELAN 
<https://tla.mpi.nl/tools/tla-tools/elan/>`_, allowing users to apply
automatic phoneme recognition to tiers in ELAN transcripts directly from
ELAN's user interface.

Requirements and installation
-----------------------------

Persephone-ELAN makes use of several of other open-source applications and
utilities:

* `ELAN <https://tla.mpi.nl/tools/tla-tools/elan/>`_ (tested with v5.6-AVFX
  and v5.7-AVFX under macOS 10.13 and 10.14)
* `Python 3 <https://www.python.org/>`_ (tested with Python 3.6)
* `ffmpeg <https://ffmpeg.org>`_

Persephone-ELAN is written in Python 3, and also depends on the following
Python packages:

* `Persephone <https://github.com/persephone-tools/persephone>`_, installed
  system-wide (currently tested with Persephone 0.3.2 under Python 3.6) and
  all of its dependencies
* `pydub <https://github.com/jiaaro/pydub>`_, installed system-wide (tested
  with v0.20.0)
  
Once all of these tools and packages have been installed, Persephone-ELAN can
be made available to ELAN as follows:

#. Save a copy of all of the files in the `latest release <https://github.com/coxchristopher/persephone-elan/releases/tag/v0.1.1>`_
   of this repository in a single directory (e.g., ``Persephone-ELAN``).
#. Edit the file ``persephone-elan.sh`` to specify (a) the absolute path of
   the Python 3 binary that Persephone-ELAN should use, (b) the directory
   in which ffmpeg is located, and (c) a Unicode-friendly language and
   locale (if ``en_US.UTF-8`` isn't available on your computer).
#. To make Persephone-ELAN available to ELAN, move your Persephone-ELAN directory
   into ELAN's ``extensions`` directory.  This directory is found in different
   places under different operating systems:
   
   * Under macOS, right-click on ``ELAN_5.7-AVFX`` in your ``/Applications``
     folder and select "Show Package Contents", then copy your ``Persephone-ELAN``
     folder into ``ELAN_5-7-AVFX.app/Contents/Java/extensions``.
   * Under Linux, copy your ``Persephone-ELAN`` folder into ``ELAN_5-7-FX/app/extensions``.
   * Under Windows, copy your ``Persephone-ELAN`` folder into ``C:\Users\AppData\Local\ELAN_5-7-FX\app\extensions``.

Once ELAN is restarted, it will now include 'Persephone Phoneme Recognizer' in
the list of Recognizers found under the 'Recognizer' tab in Annotation Mode.
The user interface for this recognizer allows users to enter the settings needed
to apply an existing, pre-trained Persephone phoneme recognition model to all of
the annotations found on a specified tier (see the `Persephone documentation
<https://persephone.readthedocs.io/en/latest/quickstart.html#training-a-toy-na-model>`_
for details on how to train these models).  All of these settings are ones that are
specified when a model is being trained (e.g., the directory in which the experiment
containing the model is found, the directory of the corpus containing the original
training data, the feature and label types used in training, etc.).

Once these settings have been entered in Persephone-ELAN, pressing the ``Start``
button will begin applying the specified Persephone phoneme recognition model to
all of the time-aligned annotations on the selected tier.  Once that process is
complete, if no errors occurred, ELAN will allow the user to load the resulting
tier with the automatically recognized phoneme strings into the current
transcript.

Limitations
-----------

This is an alpha release of Persephone-ELAN, and has only been tested under macOS
(10.13, 10.14) with Python 3.6 and Persephone 0.3.2.  No support for Windows is
included in this version.

Acknowledgements
----------------

Thanks are due to all of the contributors to Persephone, including `Oliver Adams
<https://oadams.github.io/>`_ and `Alexis Michaud <https://lacito.vjf.cnrs.fr/membres/michaud.htm>`_,
whose support and feedback contributed directly to the development of
Persephone-ELAN.  Thanks, as well, to `Han Sloetjes <https://www.mpi.nl/people/sloetjes-han>`_
for his help with issues related to ELAN's local recognizer specifications.

Citing Persephone-ELAN
----------------------

If referring to this code in a publication, please consider using the following
citation:

    Cox, Christopher. 2019. Persephone-ELAN: Automatic phoneme recognition for
    ELAN users. Version 0.1.1.

::

    @manual{cox19persephoneelan,
    title = {Persephone-ELAN: Automatic phoneme recognition for ELAN users},
    author = {Christopher Cox},
    year = {2019}
    note = {Version 0.1.1},
    }
