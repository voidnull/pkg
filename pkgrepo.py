#!/usr/bin/python
import os
import hashlib
import shutil
import glob
import subprocess
import argparse
import ConfigParser
import logging 
import sys
import SimpleHTTPServer
import SocketServer
import cgi
import re
from urlparse import urlparse, parse_qs
import tempfile

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('pkgrepo')

class PackageRepo:
    def __init__(self):
        self.conffile = None
        self.nameformat=re.compile("(.*)_([a-z0-9]+).deb")
        self.verbose = False

    def getCmdOutput(self,cmd):
        if self.verbose:
            print cmd
        p1=subprocess.Popen(cmd,stdout=subprocess.PIPE)
        return [line.strip('\n') for line in p1.stdout]
        
    def setConfigFile(self,conffile):
        self.conffile = os.path.expanduser(conffile)
        self.config = ConfigParser.SafeConfigParser();
        self.config.read(self.conffile)
        return self.verifyConf()
    
    def verifyConf(self):
        self.repodir = self.config.get('default','repodir')

        if len(self.repodir) == 0 :
            log.error("repodir needs to be specified")
            return False

        self.architectures = self.config.get('default','architectures').split(' ')
        if len(self.architectures) == 0:
            log.error("archtectures need to be specified")
            return False

        self.distname = self.config.get('default','distname')
        if len(self.distname) == 0 or not self.distname.isalpha():
            log.error("distname needs to be specified as one word")
            return False

        self.distdir = self.repodir + "/dists/" + self.distname
        
        self.branches = self.config.get('default','branches').split(' ')
        if len(self.branches) == 0:
            log.error("branches need to be specified")
            return False

        self.origin =  self.config.get('releaseinfo','origin')
        self.label =  self.config.get('releaseinfo','label')
        self.suite = self.config.get('releaseinfo','suite')
        self.codename = self.config.get('releaseinfo','codename')
        self.description =  self.config.get('releaseinfo','description')
        return True

    def setup(self):
        os.makedirs(self.repodir)
        os.makedirs(self.distdir)

        for branch in self.branches:
            for arch in self.architectures:
                os.makedirs(self.distdir + "/" + branch + "/binary-" + arch)
    
    # this is relative
    def getPackagesFile(self,branch='test',arch='amd64'):
        return "%s/binary-%s/Packages" %(branch,arch)

    def getPackageDir(self,branch='test',arch='amd64'):
        return"%s/%s/binary-%s" %(self.distdir,branch,arch)

    def getPackageLocation(self,pkgname,branch='test',arch='amd64'):
        if not pkgname.endswith(".deb"):
            # the file is just the version name_version
            pkgname = "%s_%s.deb" % (pkgname,arch)

        match = self.nameformat.match(pkgname)
        if match:
            arch = match.groups()[1]
        else:
            return None
            
        return self.getPackageDir(branch,arch) + "/" + pkgname

    def pkgExists(self,pkgname,branch='test',arch='amd64'):
        path = self.getPackageLocation(pkgname,branch,arch)
        if path == None:
            return False
        return os.path.exists(path)

    def genPackagesFile(self,justbranch=None,justarch=None):
        for branch in self.branches:
            if justbranch != None and justbranch != branch:
                continue
            for arch in self.architectures:
                if justarch !=None and justarch != arch:
                    continue
                print 'generating pkg file for %s:%s' % (branch,arch)
                os.chdir(self.repodir)
                execstring = "dpkg-scanpackages dists/%s/%s/binary-%s /dev/null > %s/%s" % (self.distname,branch,arch,self.distdir,self.getPackagesFile(branch,arch))
                ret = os.system (execstring)
                if  ret != 0:
                    print 'error : ', ret
        
                os.chdir(self.getPackageDir(branch,arch))
                ret = os.system ('gzip -c -f -q -9 Packages > Packages.gz')
                ret = os.system ('bzip2 -k -f -q -9 Packages')
                
    def genReleasesFile(self):
        os.chdir(self.distdir)
        os.system('pwd')
        for branch in self.branches:
            log.info( 'generating Release file for %s',branch)
            f = open('Releases','w')
            f.write("Origin: %s\n" %(self.origin))
            f.write("Label: %s\n" %(self.label))
            f.write("Suite: %s\n" %(self.suite))
            f.write("Codename: %s\n" %(self.codename) )
            f.write("Architectures: all\n")
            f.write("Description: %s\n" % (self.description))
        
            
            f.write("MD5Sum:\n")
            for arch in self.architectures:
                pkgfile=self.getPackagesFile(branch,arch)                
                f.write(" %s %20d %s\n" % (hashlib.md5(open(pkgfile).read()).hexdigest(),os.path.getsize(pkgfile),pkgfile))
                f.write(" %s %20d %s\n" % (hashlib.md5(open(pkgfile).read()).hexdigest(),os.path.getsize(pkgfile + '.gz'),pkgfile+'.gz'))
                f.write(" %s %20d %s\n" % (hashlib.md5(open(pkgfile).read()).hexdigest(),os.path.getsize(pkgfile + '.bz2'),pkgfile+'.bz2'))

            f.write("\n")
        
            f.write("SHA1:\n")
            for arch in self.architectures:
                pkgfile=self.getPackagesFile(branch,arch)
                f.write(" %s %20d %s\n" % (hashlib.sha1(open(pkgfile).read()).hexdigest(),os.path.getsize(pkgfile),pkgfile))
                f.write(" %s %20d %s\n" % (hashlib.sha1(open(pkgfile).read()).hexdigest(),os.path.getsize(pkgfile + '.gz'),pkgfile+'.gz'))
                f.write(" %s %20d %s\n" % (hashlib.sha1(open(pkgfile).read()).hexdigest(),os.path.getsize(pkgfile + '.bz2'),pkgfile+'.bz2'))

            f.write("\n")

            f.write("SHA256:\n")
            for arch in self.architectures:
                pkgfile=self.getPackagesFile(branch,arch)
                f.write(" %s %20d %s\n" % (hashlib.sha256(open(pkgfile).read()).hexdigest(),os.path.getsize(pkgfile),pkgfile))
                f.write(" %s %20d %s\n" % (hashlib.sha256(open(pkgfile).read()).hexdigest(),os.path.getsize(pkgfile + '.gz'),pkgfile+'.gz'))
                f.write(" %s %20d %s\n" % (hashlib.sha256(open(pkgfile).read()).hexdigest(),os.path.getsize(pkgfile + '.bz2'),pkgfile+'.bz2'))

            f.write("\n")

        f.close()

    def doneUploads(self):
        self.genPackagesFile();
        self.genReleasesFile();

    def processUploads(self,uploadsdir,branch):
        count = 0
        for srcpkg in glob.glob( "%s/*.deb" % (uploadsdir)):
            # TODO : change to move later
            match = self.nameformat.match(srcpkg)
            if not match:
                log.error("pkg name not in expected format : %s" % (srcpkg))
                continue
            arch = match.groups()[1]
            shutil.copy(srcpkg,self.getPackageDir(branch,arch))
            count += 1
        log.info ("processing [%d] packages" % (count))
        self.genPackagesFile();
        self.genReleasesFile();

    def removePackage(self,pkgname,justbranch=None,justarch=None):
        count = 0
        for branch in self.branches:
            if justbranch != None and justbranch != branch:
                continue
            for arch in self.architectures:
                if justarch !=None and justarch != arch:
                    continue
                
                pkg = self.getPackageLocation(pkgname,branch,arch)

                if os.path.exists(pkg):
                    log.warn("removing package : %s", pkg)
                    os.remove(pkg)
                    count += 1
                    self.genPackagesFile(branch,arch)
                    
        if count > 0:
            self.genReleasesFile()
        else :
            log.warn("unable to find [%s] in the repo" , pkgname)
        
    def server(self,port=8000):

        class ServerHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
            repo=None
            
            def sendOk(self):
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()

            
            def do_POST(self):                
                params=parse_qs(urlparse(self.path).query)
                print params

                branchlist=params.get('branch',[])
                branch = branchlist[0] if len(branchlist)>0 else 'test'
                if branch not in repo.branches:
                    branch='test'
                    
                files=params.get('filename',[])
                filename = files[0] if len(files)>0 else ''
                match = repo.nameformat.match(filename)
                if not match:
                    log.error("unknown file format : %s",filename)
                    self.send_error(400,"unknown file name")
                    return;

                if repo.pkgExists(filename,branch):
                    log.error("pkg already exists : %s",filename)
                    self.send_error(400,"pkg already exists")
                    return;

                content_length = int(self.headers['Content-Length'])
                filedata = self.rfile.read(content_length)
                #print filedata
                
                # store it in a temp file
                tempdir = tempfile.mkdtemp();
                temppkg= tempdir + "/" + filename
                with open(temppkg,'w') as f:
                    f.write(filedata)
                    f.close()
                    
                try :
                    # now verify the file .
                    execcmd="lintian -C deb-format " + temppkg + " 2>/dev/null"
                    log.info(execcmd)
                    ret=os.system(execcmd)
                    if ret != 0 :
                        log.error("pkg not in debian format %s" , filename)
                        self.send_error(400,"invalid deb format")
                        return
                    shutil.copyfile(temppkg,repo.getPackageLocation(filename,branch))
                finally:
                    os.remove(temppkg)
                    pass
                    
                repo.doneUploads()

                self.sendOk()

        # -- end of class ServerHandler

        os.chdir(self.repodir)
        ServerHandler.repo=self
        httpd = SocketServer.TCPServer(("", port), ServerHandler,bind_and_activate=False)
        httpd.allow_reuse_address = True
        log.info("serving at port %d",port)
        try :
            httpd.server_bind()
            httpd.server_activate()
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass;
        finally:
            httpd.server_close()
            
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Simple Debian Repository',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c','--conf', help ="Conf file")
    parser.add_argument('-v','--verbose', action="store_true")

    parser.add_argument('--setup', action="store_true" , help = "initialize a repo")
    parser.add_argument('--server', action="store_true", help = "run http server")
    parser.add_argument('--remove', default = None , help = "delete a package")
    parser.add_argument('-p','--port', type=int, help = "server port" , default=8000)

    args = parser.parse_args()

    if args.conf == None :
        log.error("conf file needs to be specified")
        parser.print_usage()
        sys.exit(0)


    if not (args.setup or args.remove or args.server) :
        log.error("no action specified ..")
        parser.print_usage()
        sys.exit(0)

    repo = PackageRepo()
    if not repo.setConfigFile(args.conf):
        log.error ( "error with config file")
        sys.exit(1)

    if args.setup:
        repo.setup()

    if args.remove:
        repo.removePackage(args.remove)

    if args.server:
        repo.server(args.port)
