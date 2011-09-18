=======================
Gunicorn HUP on change
=======================

This script is intended to help people who develop applications using
Gunicorn_ by automatically sending an HUP signal to the master process
when python files are changed.

.. _Gunicorn: http://gunicorn.org/


Please note that this script **only works on a Linux OS**, mainly because it uses pyinotify_

.. _pyinotify: https://github.com/seb-m/pyinotify

------

Simplest example::

  ./gunicorn_hup_on_change.py

Will restart the first gunicorn master process it finds,
and will watch for modifications in the current python path.

------


If you want to watch specific directories, you can use the following::

  ./gunicorn_hup_on_change.py ./lib/ ./ext/lib/

------


You can also target a specific gunicorn process using `-a`, in case
you have multiple gunicorn instances running::

  ./gunicorn_hup_on_change.py -a my_app

Will search for a process "named" `gunicorn: master [my_app]`


------

By default, the watcher will wait 500ms after a file's modification to send the
HUP signal, to avoid sending multiple signals when you update a batch of files
(when updating your repository for example).
You can change this interval with the `-w` option

.. vim: et ts=2 sw=2
