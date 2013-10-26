Inspiration
===========
These tools were written after I had fell in love with Yahoo!s internal package management tool : YINST.

pkg.py
======

- Helper script to get info about packages installed.
- easier set of commands to remember that dpkg/apt-get 

```
usage:
pkg.py cmd [options] [[pkgname]...] [file] [program-options]
   cmd :-
       ls    : list packages
       info  : display pkg information
       help  : display this menu
       which : show which pkg contains the file
   options :-
       --files  : for ls , list files in the pkg
       [file]   : for ls , if a file is specified, it will print the pkg that owns it
   program-options:
             : all these will be sent to the subprocess

```

pkgcreate.py
============

- A simple tool to easily create debian packages from a pkg definition file. 
- This will allow the pkgdef file to be checked in along with the code
- easy to maintain

```
usage: pkgcreate.py [-h] [-v] [-k] ...

Debian Pkg Maker

positional arguments:
  pkgfiles

optional arguments:
  -h, --help      show this help message and exit
  -v, --verbose   be more verbose (default: False)
  -k, --keeptemp  keep temporary files (default: False)

```

Format for pkgdef
=================

- For all values, any value between backticks will be evaluated as shell commands


```
########################################################################
# Meta information
# meta-name [=] meta-value
########################################################################
Package = mytestpkg
Version = `grep ^Version ChangeLog | head -n1 | awk {print $2}`
Maintainer = myname <myemailid@domain.com>
Description = Hi! This is a test pkg

########################################################################
# List of files to be packaged
# format: file [=] [conf] [perms=655] destfile [srcfile ... ]
# srcfile : if empty or more than 1 then 
#         : destfile will be created as a directory
# conf : mark this file as a conf file
# perms : NOT IMPLEMENTED
########################################################################

file = /tmp/shell/test1.sh ../shell/test1.sh
file = /tmp/shell1/test.sh  ../shell/test.sh
file = /usr/include/test   ./myfiles/*.h

post-install = ./install.sh
pre-install  = ./install.sh
post-remove  = ./install.sh
pre-remove   = ./install.sh

#service - NOT IMPLEMENTED

```

Pkg Repo
============

- Whole pkg repo management in one file
- in built http interface
- upload packages via http.
- to upload just post the pkg to http://localhost:8000?name=pkgname 

```
usage: pkgrepo.py [-h] [-c CONF] [-v] [--setup] [--server] [--remove REMOVE]
                  [-p PORT]

Simple Debian Repository

optional arguments:
  -h, --help            show this help message and exit
  -c CONF, --conf CONF  Conf file (default: None)
  -v, --verbose
  --setup               initialize a repo (default: False)
  --server              run http server (default: False)
  --remove REMOVE       delete a package (default: None)
  -p PORT, --port PORT  server port (default: 8000)

```


Setup
=====
- create a conf file as below
- run `pkgrepo.py -c conffile --server -p 8000`
- browse your repo at http://localhost:8000
- upload :
  - `curl --request POST --data-binary @testpkg_1.2.deb http://localhost:8000?name=testpkg_1.2&branch=stable`

Pkg Repo Conf File
==================
```
[default]
# absolute path of the repo directory
repodir = /var/lib/package-repo

# supported architectures
architectures = amd64 i386 all

# name of the distribution [oneword]
distname = personal

# supported branches/components
branches = stable test

[releaseinfo]
Origin =  Your Name
Label =  My Personal software
Suite =  hacks
Codename = test
Description =  My Personal releases
```