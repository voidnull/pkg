#!/usr/bin/env python
import shlex
import os
import shutil
import tempfile
import re
import subprocess
import glob
import logging
import argparse
import types
import sys

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('pkg')

class FileItem:
    def __init__(self):
        self.perms= None
        self.src  = None
        self.dest = None
        self.dir  = False
        self.owner= None
        self.conf = False

class PkgCreate:
    def __init__(self):
        self.metadata=dict()
        self.files = []
        self.dirs  = []
        self.META_PACKAGE     = 'package' 
        self.META_MAINTAINER  = 'maintainer'
        self.META_VERSION     = 'version'
        self.META_DESCRIPTION = 'description'
        self.META_DEPENDS     = 'depends'
        self.META_REPLACES    = 'replaces'

        self.META_POSTINSTALL = 'post-install'
        self.META_PREINSTALL  = 'pre-install'
        self.META_POSTREMOVE  = 'post-remove'
        self.META_PREREMOVE   = 'pre-remove'
        
        self.controlname = dict()
        self.controlname[self.META_POSTINSTALL] = 'postinst' 
        self.controlname[self.META_PREINSTALL]  = 'preinst' 
        self.controlname[self.META_POSTREMOVE]  = 'postrm' 
        self.controlname[self.META_PREREMOVE]   = 'prerm' 

        self.metadata[self.META_DEPENDS]=[]
        self.verbose = False
        self.pkgdir=None
        self.keepTemp = False
        pass;
        
    def tokenize(self,line):
        # first expand any shell ``
        st=line.find('`')
        if st >= 0:
            end = line.find('`',st+1)
            if end>st:
                out=self.getCmdOutput(line[st+1:end])
                line=line[:st] + ' ' + ' '.join(out) + ' ' + line[end+1:]
                
        lexer = shlex.shlex(line)
        lexer.wordchars += './-\\'
        return list(lexer)

    def debug(self,data):
        if self.verbose:
            log.info(data)

    def getCmdOutput(self,cmd,shell=True):
        if self.verbose:
            print cmd
        p1=subprocess.Popen(cmd,stdout=subprocess.PIPE,shell=shell)
        return [line.strip('\n') for line in p1.stdout]

    def process(self,filename):
        log.info("processing : %s", filename)
        try:
            lines = [line.strip() for line in open(filename)]
            try :
                n = 0
                curline = ''
                for line in lines:
                    curline = line
                    n += 1
                    tokens = self.tokenize(line)
                    if len(tokens)>0:
                        self.processTokens(tokens)
            except :
                log.error("process error on line [%d] : [%s] ", n, curline)
                return 
            self.debug("metadata = %s" % (self.metadata))
            self.debug("files = %s" %(self.files))
            if self.verify():
                self.makePkgDir()
                self.makePkg()
        finally:
            if self.pkgdir != None and not self.keepTemp:
                shutil.rmtree(self.pkgdir,True)

    def processTokens(self,tokens):
        try :
            key = tokens[0].lower()
            n = 1
            if key in [ 'package' ,'maintainer','version','description','depends','file']:
                if tokens[n] in [':','=']:
                    n += 1

                if key == 'file':
                    fileItem =FileItem()

                    # parse options
                    while n < len(tokens) and tokens[n] in [ 'perms', 'owner', 'conf' ] :
                        if  tokens[n] == 'perms' :
                            n += 1
                            if tokens[n] in ['=']:
                                n += 1
                            fileItem.perms=tokens[n]
                            n += 1
                        elif tokens[n] == 'conf' :
                            n += 1
                            if tokens[n] in ['=']:
                                n += 2 # ignore the following token
                            fileItem.conf = True
                            
                        elif tokens[n] == 'owner' :
                            n += 1
                            if tokens[n] in ['=']:
                                n += 1
                            fileItem.owner=tokens[n]
                            n += 1
                            if ':' == tokens[n] :
                                fileItem.owner += ':' + tokens[n+1]
                                n += 2

                    fileItem.dest=tokens[n]
                    n += 1
                    
                    if n >= len(tokens):
                        # this is a dir
                        fileItem.dir = True
                        self.files.append(fileItem)
                        return

                    fileItem.src=[]
                    for token in tokens[n:]:
                        fileItem.src.extend(glob.glob(token))
                    
                    if len(fileItem.src) == 1 :
                        if tokens[n] != fileItem.src[0]:
                            fileItem.dir = True
                            # the dest had a wildcard but only one file was matched
                            log.warn("wildcard expanded to only one file : %s ", fileItem.src[0])

                    elif len(fileItem.src) > 1 :
                        log.warn("dest [%s] will be treated as a directory",fileItem.dest)
                        if fileItem.dest.find('.') >=0 :
                            log.warn("dest directory has a . in its name [%s]", fileItem.dest)
                    self.files.append(fileItem)
                elif key == 'depends':
                    self.metadata[key].append(' '.join(tokens[n:]))
                else:
                    self.metadata[key] = ' '.join(tokens[n:])
            elif key in [self.META_POSTINSTALL, self.META_PREINSTALL, self.META_POSTREMOVE, self.META_PREREMOVE]:
                if tokens[n] in [':','=']:
                    n += 1
                self.metadata[key] = tokens[n]
            else:
                log.warn("unknown key : [%s]" % (key))
        except :
            log.error("unable to process tokens %s ", tokens)
            raise

    def verify(self):
        # check for meta data

        #https://www.debian.org/doc/debian-policy/ch-controlfields.html#s-f-Source
        if self.META_PACKAGE in self.metadata:
            p = re.compile('^[a-z0-9][a-z0-9-\.]+$')
            if None == p.match(self.metadata[self.META_PACKAGE]) or len (self.metadata[self.META_PACKAGE]) < 5:
                log.error("invalid package name [%s] : lowercase, (a-z,0-9,+-.) and len >= 5 " % (self.metadata[self.META_PACKAGE]))
                return False
        else:
            log.error("meta : %s : missing"  % (self.META_PACKAGE))
            return False

        if self.META_VERSION in self.metadata:
            p = re.compile('^[0-9][a-z0-9-\.]+$')
            if None == p.match(self.metadata[self.META_VERSION]):
                log.error( "invalid version [%s] : [^[0-9][a-z0-9-\.]+$] " % (self.metadata[self.META_VERSION]))
                return False
        else:
            log.error("meta : %s : missing"  % (self.META_VERSION))
            return False

        if self.META_DESCRIPTION in self.metadata:
            if len (self.metadata[self.META_DESCRIPTION]) < 5:
                log.error("please add more info in description")
                return False
        else:
            log.error("meta : %s : missing"  % (self.META_DESCRIPTION))
            return False

        if self.META_MAINTAINER in self.metadata:
            self.metadata[self.META_MAINTAINER] = self.metadata[self.META_MAINTAINER].replace("< ","<")
            self.metadata[self.META_MAINTAINER] = self.metadata[self.META_MAINTAINER].replace(" >",">")
            self.metadata[self.META_MAINTAINER] = self.metadata[self.META_MAINTAINER].replace(" @ ","@")

            p = re.compile('^[a-z0-9-\._ ]+ <[a-z0-9-\._]+@[a-z0-9-\._]+>$')
            if None == p.match(self.metadata[self.META_MAINTAINER]) :
                log.error("invalid maintainer [%s] :- name <email>" % (self.metadata[self.META_MAINTAINER]) )
                return False
        else:
            log.error("meta : %s : missing .. so adding default"  % (self.META_MAINTAINER))
            return False

        if self.META_DEPENDS in self.metadata and len(self.metadata[self.META_DEPENDS])>0:
            p=re.compile('^[a-z0-9][a-z0-9-\.]+ ([<>=]*)$')
            for n in range(0,len(self.metadata)):
                depends = self.metadata[self.META_DEPENDS][n].replace('( ','(').replace(' )',')')
                self.metadata[self.META_DEPENDS][n] = depends
                
                if None == p.match(depends):
                    log.error("invalid depends [%s] : ^[a-z0-9][a-z0-9-\.]+ ([<>=]*)$ " % (depends))
                return False

        # check all the files
        for item in self.files:
            if not item.dir:
                for f in item.src:
                    if not os.path.exists(f):
                        log.error('unable to locate file [%s]',f)
                        return False

        # check the install scripts
        for key in [self.META_POSTINSTALL, self.META_PREINSTALL, self.META_POSTREMOVE, self.META_PREREMOVE]:
            if key in self.metadata:
                if not os.path.exists(self.metadata[key]):
                    log.error('unable to locate file [%s]',self.metadata[key])
                    return False
        return True

    def writeControlFiles(self,debianDir):
        with open(debianDir + '/control','w') as f: 
            f.write('Package: %s\n' % (self.metadata[self.META_PACKAGE]))
            f.write('Version: %s\n' % (self.metadata[self.META_VERSION]))
            f.write('Maintainer: %s\n' % (self.metadata[self.META_MAINTAINER]))
            f.write('Description: %s\n' %(self.metadata[self.META_DESCRIPTION]))
            output = self.getCmdOutput('dpkg --print-architecture')
            f.write('Architecture: %s\n' % (output[0]))
            
            if len(self.metadata[self.META_DEPENDS]) > 0 :
                f.write('Depends: ')
                maxlen=len(self.metadata[self.META_DEPENDS])
                for n in range(0,maxlen):
                    depends = self.metadata[self.META_DEPENDS][n]
                    f.write(depends)
                    if n < (maxlen-1):
                        f.write(', ')
                f.write('\n')

        with open(debianDir + '/conffiles','w') as f:
            for f in self.files:
                if f.conf:
                    f.write('%s\n' % (f.dest))

        for key in [self.META_POSTINSTALL, self.META_PREINSTALL, self.META_POSTREMOVE, self.META_PREREMOVE]:
            if key in self.metadata:
                shutil.copy2(self.metadata[key] , debianDir + '/' + self.controlname[key])

    def makePkg(self):
        debfile="%s_%s.deb" % (self.metadata[self.META_PACKAGE],self.metadata[self.META_VERSION])
        log.info('creating %s' % (debfile))
        subprocess.call(['dpkg-deb', '--build', self.pkgdir ,debfile])

    def makePkgDir(self):
        self.pkgdir=tempfile.mkdtemp(dir="./")
        self.debug("pkgdir = %s" %( self.pkgdir))
        for item in self.files:
            dest = self.pkgdir + item.dest
            if item.dir:
                self.debug('making dir : %s', self.dest)
                os.makedirs(dest)
                for f in item.src:
                    self.debug("copy: src: %s, dest: %s " %(f,dest))
            else :
                destdir = os.path.dirname(dest)
                self.debug ('destfile: %s , destdir: %s' % ( dest , destdir))
                os.makedirs(destdir)
                self.debug("copy: src: %s, dest: %s " %(item.src[0],dest))
                shutil.copy2(item.src[0],dest)

        debianDir = self.pkgdir + "/DEBIAN"
        os.mkdir(debianDir)
        self.writeControlFiles(debianDir)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Debian Pkg Maker',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-v','--verbose', action="store_true" , default=False, help = "be more verbose" )
    parser.add_argument('-k','--keeptemp', action="store_true", default=False, help = "keep temporary files")
    parser.add_argument('pkgfiles', nargs=argparse.REMAINDER)

    args = parser.parse_args()

    pkg=PkgCreate()
    pkg.verbose  = args.verbose
    pkg.keepTemp = args.keeptemp

    if len(args.pkgfiles) == 0:
        args.pkgfiles = glob.glob('*.pkgdef')

    if len(args.pkgfiles) == 0:
        log.error("no .pkgdef files found..")
        sys.exit(0)

    for pkgfile in args.pkgfiles:
        pkg.process(pkgfile)
