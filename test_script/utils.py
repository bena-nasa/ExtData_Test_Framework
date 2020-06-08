#!/usr/bin/env python

"""
# ------------------------------------------------------------------------------
# collection of useful functions:
#
#      get_mapl_times
#      get_mapl_memusage
#      get_wall_cpu_times
#      find_files
#      writemsg
#      get_hostname
#      mkdir_p
#      create_link
#      cvs_setenv
#      cvs_update
#      cvs_checkout
#      source_g5_modules
#      isFloat
#      isInt
#      get_model_tag
#      print_dict
#      build_parallel
#      build_serial
#      build_pinstall
#      build_cmake_developer
#      check_bld
#      build_doc
#      check_doc
#      submit_job
#      check_egress
#      create_setup_input
#      get_file_contents
#      write_file_contents
#      run_setup_script
#      copy_rst
#      edit_cap_rc_gcm_run_j
#      bootstrapAGCM
#      useSatsim
#      useReplay
#      useDasmode
#      edit_gcm_regress_j
#      edit_co2_gridcomp_rc
#      check_lt_test
#      createDirs
#      job_completed
#      git_clone
#      useHemco
#      useOpsGOCART
#      are_dir_trees_equal
#      useSingleNode
#      is_tool
#      nc4_compare
#      nccmp_compare
#      cdo_compare
#      cmp_compare
# ------------------------------------------------------------------------------
"""


import os
import sys
import glob
import time
import shutil
import errno
import fnmatch
import subprocess as sp
import filecmp
import shlex
import distutils.spawn
import subprocess
import re

from datetime import datetime
from collections import OrderedDict

def get_mapl_times(PBSOutputFile, GridComps, What2Report='TOTAL'):
    """
    # --------------------------------------------------------------------------
    # parse PBS output file for MAPL times (as reported by MAPL timer)
    #
    # Inputs:
    #     PBSOutputFile: job output file
    #         GridComps: list of GridComps whose times we want
    #       What2Report: One of TOTAL/GenInitTot/GenFinalTot etc.
    #
    # Output:
    #        MAPL_times: a dict with GridComp as key and time as val
    # --------------------------------------------------------------------------
    """
    
    assert GridComps, 'empty list passed'

    MAPL_Times = OrderedDict()
    fin = open(PBSOutputFile, 'r')
    lines = fin.readlines()
    
    endString = '--GenRefreshMine'
    for GridComp in GridComps:
        if GridComp == 'EXTDATA': What2Report = 'Run'
        startString = 'Times for ' + GridComp
        TotalTime = 0
        GenInitTot = 0
        GenFinalTot = 0
        inBlock = False
        TimeTaken = 0
        for i in range(len(lines)):
            if startString in lines[i]: inBlock = True
            if endString in lines[i]: inBlock = False

            # inside time block
            if inBlock:
                spltLine = [x.strip() for x in lines[i].split(':')]
                if spltLine[0]==What2Report: TimeTaken = float(spltLine[1].split()[-1])
        
        MAPL_Times[GridComp] = TimeTaken

    fin.close()

    return MAPL_Times


def get_mapl_memusage(PBSOutputFile, GridComps):
    """
    # --------------------------------------------------------------------------
    # parse PBS output file for MAPL memory usage (reported by MAPL memutils)
    #
    # Inputs:
    #     PBSOutputFile: job output file
    #         GridComps: list of GridComps whose mem usage we want
    #
    # Output:
    #     a list of two dicts
    #     MAPL_CAP_Mems: a dict with keys 'high water mark', 
    #                    'mem used', 'swap used'. Corresponding values are
    #                    lists of memory use as reported by MAPL_Cap:TimeLoop
    #                    return empty dict if mem usage not found
    #      MAPL_GC_Mems: a dict with key: GridComp and val: high water mark
    # --------------------------------------------------------------------------
    """
    
    assert GridComps, 'empty list passed'

    MAPL_CAP_Mems = OrderedDict()
    MAPL_GC_Mems = OrderedDict()

    date = []
    time = []
    hwm = []
    mem_used = []
    swap_used = []

    fin = open(PBSOutputFile, 'r')
    lines = fin.readlines()
    
    for line in lines:        
        str2chk_1 = 'Memuse(MB) at MAPL_Cap:TimeLoop'
        str2chk_2 = 'Mem/Swap Used (MB) at MAPL_Cap:TimeLoop'
        str2chk_3 = 'AGCM Date:'
        if str2chk_1 in line:
            tmphwm = line.split('=')[1].strip().split()[0]
            hwm.append(float(tmphwm))
        if str2chk_2 in line:
            tmpmem, tmpswap = line.strip().split('=')[1].split()
            mem_used.append(float(tmpmem))
            swap_used.append(float(tmpswap))
        if str2chk_3 in line:
            date.append(line.strip().split()[2])
            time.append(line.strip().split()[4])

    for GridComp in GridComps:
        for i in range(len(lines)):
            line = lines[i]
            str2chk = 'Memuse(MB) at '+ GridComp + 'MAPL_GenericInitialize'
            if str2chk in line:
                MAPL_GC_Mems[GridComp] = float(line.strip().split('=')[1].split()[0])
                break
            else:
                MAPL_GC_Mems[GridComp] = -999.99

    fin.close()

    # dict to be returned
    if hwm and mem_used and swap_used:
        MAPL_CAP_Mems ={'date': date,
                        'time': time,
                        'high water mark': hwm, 
                        'mem used': mem_used,
                        'swap used': swap_used}

    return [MAPL_CAP_Mems, MAPL_GC_Mems]



def get_wall_cpu_times(PBSOutputFile):
    """
    # --------------------------------------------------------------------------
    # parse PBS output file for Wall and CPU times
    #
    # Inputs:
    #     PBSOutputFile: job output file
    #
    # Output:
    #         PBS_times: a dict with keys 'wall time' and 'cpu time' with
    #                    values in seconds (float)
    # --------------------------------------------------------------------------
    """
    
    PBS_times = {'wall time': '', 'cpu time': ''}
    fin = open(PBSOutputFile, 'r')
    lines = fin.readlines()

    for line in lines:
        if 'Walltime Used' in line:
            assert not PBS_times['wall time']
            hh, mm, ss = line.split(':')[-3:]
            if '-' in hh:
                dd, hh = hh.split('-')
            else:
                dd = '0'
            PBS_times['wall time'] = int(dd)*24*3600 + float(hh)*3600 + float(mm)*60 + float(ss)
        if 'CPU Time Used' in line:
            assert not PBS_times['cpu time']
            hh, mm, ss = line.split(':')[-3:]
            if '-' in hh:
                dd, hh = hh.split('-')
            else:
                dd = '0'
            PBS_times['cpu time'] = int(dd)*24*3600 + float(hh)*3600 + float(mm)*60 + float(ss)
    fin.close()

    return PBS_times


def find_files(srcdir, pattern):
    """
    # --------------------------------------------------------------------------
    # find files under 'srcdir' matching 'pattern'
    #
    # Inputs:
    #       srcdir: look for files under this dir
    #      pattern: look for files matching this pattern
    # Output:
    #      list of matched files
    # --------------------------------------------------------------------------
    """

    matched_files = []
    for root, dirs, files in os.walk(srcdir):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                filename = os.path.join(root, basename)
                matched_files.append(filename)
    return matched_files



def writemsg(str2write, fout=None, quiet=None):
    """
    # --------------------------------------------------------------------------
    # write message to fout
    #
    # Inputs:
    #    str2write: (obvious)
    #         fout: handle of (open) output file, if None, set to sys.stdout
    # --------------------------------------------------------------------------
    """    
    if not fout: fout = sys.stdout
    if not quiet: fout.write('%s' % str2write); fout.flush()



def get_hostname():
    """
    # --------------------------------------------------------------------------
    # Return the hostname (DISCOVER, PLEIADES)
    # --------------------------------------------------------------------------
    """

    node = os.uname()[1]
    if node[0:8]=='discover' or node[0:4]=='borg':
        HOST = 'DISCOVER'
    elif node[0:3]=='pfe' or node[0:4]=='maia' or (node[0]=='r' and node[4]=='i'):
        HOST = 'PLEIADES'
    elif node[-13:]=='gsfc.nasa.gov' or (node[:6]=='gs6101' 
            and (node[-12:]=='ndc.nasa.gov') or node[-5:]=='local'):
        HOST = 'DESKTOP'
        # MAT Note that the DESKTOP is a "failover" if it is gsfc
        #     we return DESKTOP if it matches nothing else
    else:
        HOST = 'DESKTOP'
        #raise Exception('could not get host name from node [%s]' % node)

    return HOST



def mkdir_p(path):
    """
    # --------------------------------------------------------------------------
    # implements 'mkdir -p' functionality
    #
    # Inputs:
    #     path: path to dir to be created
    # Output:
    #     dir is created
    # --------------------------------------------------------------------------
    """    

    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST:
            pass
        else: raise



def create_link(TARGET, DIRECTORY, LINK_NAME):
    """
    # --------------------------------------------------------------------------
    # create link LINK_NAME to TARGET in DIRECTORY. 
    # implements the 'ln -s TARGET DIRECTORY/LINK_NAME' functionality
    # --------------------------------------------------------------------------
    """    
    
    cmd = ['ln', '-s', TARGET, DIRECTORY + '/' + LINK_NAME]
    run = sp.check_call(cmd)



def cvs_setenv(fout=None):
    """
    # --------------------------------------------------------------------------
    # set cvs environment
    #
    # Input:
    #    fout: handle of open output file, if None - set to sys.stdout
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout
    
    writemsg(' Setting CVS env...', fout)

    HOST = get_hostname()
    UNAME = os.environ['LOGNAME']


    if HOST in ['DISCOVER', 'PLEIADES']:
        os.environ['CVSROOT'] = ':ext:%s@cvsacldirect:/cvsroot/esma' % UNAME
    else:
        raise Exception('host [%s] not recognized' % HOST)
    os.environ['CVS_RSH'] = 'ssh'

    writemsg('done.\n', fout)



def cvs_update(TAG, MOD=None, fout=None):
    """
    # --------------------------------------------------------------------------
    # query files that need to be updated and update those files
    # NOTE: needs to be called from src directory
    # 
    # Input:
    #           TAG: CVS tag to check for new files
    #           MOD: Module directory being updated
    #          fout: handle of open output file, if None - set to sys.stdout
    # Output:
    #     returns True if files were updated, else returns False
    # --------------------------------------------------------------------------
    """
    
    if not fout: fout = sys.stdout

    if MOD:
        writemsg(' Updating %s to %s...' % (MOD, TAG), fout)
    else:
        writemsg(' Updating to %s...' % TAG, fout)

    # first query files that need to be updated
    # -----------------------------------------
    cmd = ['cvs', '-nq' , 'up', '-r', TAG]
    run = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)
    output = run.communicate()
    rtrnCode = run.wait()
    if rtrnCode != 0:
        print('0:'); print(output[0]); print('1:'); print(output[1])
        raise Exception('CVS update query failed')
    updFiles = []
    changedFiles = output[0].split('\n')
    for i in range(len(changedFiles)):
        file = changedFiles[i]
        if not file:
            break
        if file[0]=='U':
            updFiles.append(file.split(' ')[1])
    if len(updFiles)==0:
        writemsg('nothing to upd.\n', fout)
        return False

    # now, update
    # -----------
    for i in range(len(updFiles)):
        cmd = ['cvs', 'up', '-r', TAG, updFiles[i]]
        run = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)
        output = run.communicate()
        rtrnCode = run.wait()
        if rtrnCode != 0:
            print('0:'); print(output[0]); print('1:'); print(output[1])
            raise Exception('CVS update failed for file [%s]' % updFiles[i])    

    writemsg('done.\n', fout)

    # print list of updated files
    # ---------------------------
    writemsg(' Updated files tagged with %s:\n' % TAG, fout)
    for i in range(len(updFiles)):
        writemsg('   %s\n' % updFiles[i], fout)

    return True



def cvs_checkout(TAG, MOD, DIR=None, fout=None):
    """
    # --------------------------------------------------------------------------
    # Checkout model from CVS repository.
    # NOTE: Checks out model in the directory it is called from and returns
    # output of cvs command
    # 
    # Input:
    #            TAG: CVS tag to check out
    #            MOD: Corresponding module
    #            DIR: Check out into DIR instead, if None checkout into MOD
    #           fout: handle of open output file, if None - set to sys.stdout
    # Output:
    #         output: list containing output of command (stdout and stderr)
    #  
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout

    writemsg(' Checking out [tag: %s, module: %s]...' % (TAG, MOD), fout)

    if DIR: cmd = ['cvs', 'co', '-P', '-r', TAG, '-d', DIR, MOD]
    else: cmd = ['cvs', 'co', '-P', '-r', TAG, MOD]
    run = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)

    output = run.communicate()
    rtrnCode = run.wait()
    if rtrnCode != 0:
        print('0:'); print(output[0]); print('1:'); print(output[1])
        raise Exception('CVS checkout failed')

    writemsg('done.\n', fout)
    return output



def source_g5_modules(g5_modules, fout=None):
    """
    #---------------------------------------------------------------------------
    # def source_g5_modules(g5_modules, fout):
    #
    # source_g5_modules is a wrapper for the csh script g5_modules. It
    # queries the csh script for basedir, modules and modinit, adds basedir
    # to os.environ and loads library modules
    # 
    # Input:
    #    g5_modules: full path of g5_modules
    #          fout: handle of (open) log file, if None - set to sys.stdout
    #---------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout

    # check if g5_modules exists
    # --------------------------
    if not os.path.isfile(g5_modules):
        raise Exception('g5_modules does not exist')


    # part of the command to run
    # --------------------------
    cmd = ['/bin/csh', g5_modules]


    # query for basedir
    # -----------------
    run = sp.Popen(cmd+['basedir'], stdout=sp.PIPE, stderr=sp.PIPE)
    output = run.communicate()
    rtrnCode = run.wait()
    if rtrnCode != 0:
        print('0:'); print(output[0]); print('1:'); print(output[1])
        raise Exception('cant query g5_modules for basedir')
    #BASEDIR = output[0].strip()
    BASEDIR = output[0].split('\n')[0].strip()


    # query for modules to load
    # -------------------------
    run = sp.Popen(cmd+['modules'], stdout=sp.PIPE, stderr=sp.PIPE)
    output = run.communicate()
    rtrnCode = run.wait()
    if rtrnCode != 0:
        print('0:'); print(output[0]); print('1:'); print(output[1])
        raise Exception('cant query g5_modules for modules')
    #MODULES = output[0].strip().split()
    MODULES = output[0].split('\n')[0].strip().split()

    #print("MATMAT MODULES: ", MODULES)


    # query for modinit
    # -----------------
    run = sp.Popen(cmd+['modinit'], stdout=sp.PIPE, stderr=sp.PIPE)
    output = run.communicate()
    rtrnCode = run.wait()
    if rtrnCode != 0:
        print('0:'); print(output[0]); print('1:'); print(output[1])
        raise Exception('cant query g5_modules for modinit')
    # MODINIT = output[0].strip().replace('csh', 'python')
    # For Matt, modinit query results in '/usr/share/modules/init/csh\n/usr/..'
    tmpdir = output[0].split('\n')[0].strip()
    newdir = tmpdir.split('/')
    HOST = get_hostname()
    # MAT On anvil, at least, the modules has python.py
    if HOST=='PLEIADES' or HOST=='DESKTOP':
        newdir[-1] = 'python.py'
    else:
        newdir[-1] = 'python'
    MODINIT = '/'.join(newdir)
    #print 'MODINIT:', MODINIT
    #if not os.path.isfile(MODINIT):
        #raise Exception('cant see %s' % MODINIT)


    # set BASEDIR
    # -----------
    ARCH = os.uname()[0]
    writemsg(' %s: Setting BASEDIR' % os.path.basename(g5_modules), fout)
    os.environ['BASEDIR'] = BASEDIR # this only modifies the local environment
    BASELIB = '%s/%s/lib' % (BASEDIR, ARCH)
    if 'LD_LIBRARY_PATH' in os.environ:
        os.environ['LD_LIBRARY_PATH'] += os.pathsep + BASELIB
    else:
        os.environ['LD_LIBRARY_PATH'] = BASELIB


    # load library modules
    # --------------------
    if (os.path.isfile(MODINIT)):
        writemsg(' and modules.\n', fout)

        exec(open(MODINIT).read())
        module('purge')
        for mod in MODULES:
            module('load',mod)

        # At NAS something weird is happening with python
        # if you force it to load this at the end, things work
        #if HOST=='PLEIADES':
            #module('load','python/2.7.15')
        #module('list')
    elif os.environ.get('LMOD_PKG') is not None:
        writemsg(' and modules.\n', fout)

        sys.path.insert(0,os.path.join(os.environ['LMOD_PKG'], "init"))
        from env_modules_python import module

        module('purge')
        for mod in MODULES:
            module('load',mod)

    else:
        raise Exception('could not load required modules')

    # set ESMA_FC to gfortran, if needed
    # ----------------------------------
    if BASEDIR.split(os.sep)[-1].split('_')[0]=='gfortran':
        writemsg(' Setting ESMA_FC to gfortran\n', fout)
        os.environ['ESMA_FC'] = 'gfortran'

    # set ESMA_FC to pgfortran, if needed
    # -----------------------------------
    if BASEDIR.split(os.sep)[-1].split('_')[0]=='pgfortran':
        writemsg(' Setting ESMA_FC to pgfortran\n', fout)
        os.environ['ESMA_FC'] = 'pgfortran'
        os.environ['PGI_LOCALRC'] = '/discover/swdev/mathomp4/PGILocalRC/linux86-64/17.10/bin/localrc.60300'
        writemsg(' Setting PGI_LOCALRC to %s\n' % os.environ['PGI_LOCALRC'], fout)
        

#     # check to see ESMA_FC is set to pgfortran
#     # if set, add it to os.environ (default ifort)
#     # --------------------------------------------
#     if os.environ.has_key('ESMA_FC'):
#         del os.environ['ESMA_FC']
#     fin = open(g5_modules)
#     for line in fin:
#         if 'pgfortran' in line:
#             os.environ['ESMA_FC'] = 'pgfortran'
#             writemsg(' Setting ESMA_FC to pgfortran\n', fout)
#             break
#     fin.close()



def isFloat(string):
    """
    #---------------------------------------------------------------------------
    # def isFloat(string):
    #
    # Check if input string is float. If float, return True, else return False
    # Input:
    #        string: string to check
    # Output:
    #     True if input is float, else False
    #---------------------------------------------------------------------------
    """

    try:
        float(string)
        return True
    except ValueError:
        return False



def isInt(string):
    """
    #---------------------------------------------------------------------------
    # def isInt(string):
    #
    # Check if input string is int. If int, return True, else return False
    # Input:
    #        string: string to check
    # Output:
    #     True if input is an integer, else False
    #---------------------------------------------------------------------------
    """

    try:
        int(string)
        return True
    except ValueError:
        return False



def get_model_tag(BLD_ROOT):
    """
    #---------------------------------------------------------------------------
    # def get_model_tag(BLD_ROOT):
    #
    # Retrieve the model tag from the specified bld. For AGCM, BLD_ROOT is the
    # path to the dir containing GEOSagcm
    #
    # Input:
    #        BLD_ROOT: Root of build directory
    # Output:
    #     return the model tag as a string if found, else return None
    #---------------------------------------------------------------------------
    """

    TAG_FILE = BLD_ROOT + '/GEOSagcm/src/CVS/Tag'
    if os.path.isfile(TAG_FILE):
        return open(TAG_FILE).read()[1:].strip()
    else:
        return None

    return True



def print_dict(d, fout=None):
    """
    #---------------------------------------------------------------------------
    # def print_dict(d, fout):
    #
    # print dict d to fout (open file handle)
    #
    # Input:
    #        d: dict to print
    #     fout: (open) file handle, can be sys.stdout
    #---------------------------------------------------------------------------
    """
    if not fout: fout = sys.stdout

    for key in list(d.keys()):
        writemsg('%15s: %s\n' % (key, d[key]), fout)



def build_parallel(SRC_DIR, GPU=False, PGI=False, DEBUG=False, fout=None):
    """
    #---------------------------------------------------------------------------
    # def build_parallel(SRC_DIR, fout):
    #
    # Build model using the parallel_build.csh script
    #
    # Inputs:
    #  SRC_DIR: source dir (contains parallel_build.csh)
    #     fout: (open) file handle, if None, it is set to sys.stdout
    #
    #---------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout

    # Discover or Pleiades
    # --------------------
    HOST = get_hostname()

    # get current dir and switch to src dir
    # -------------------------------------
    CWD = os.getcwd()
    os.chdir(SRC_DIR)
    
    writemsg(' Building model (parallel)...', fout)

    # source g5_modules
    # -----------------
    G5_MODULES = SRC_DIR + os.sep + 'g5_modules'
    source_g5_modules(G5_MODULES)

    # set ESMADIR
    # -----------
    os.environ['ESMADIR'] = SRC_DIR + '/..'

    # delete existing pbld outputs
    # ----------------------------
    outFiles = glob.glob(SRC_DIR + '/parallel_build.o*')
    for file in outFiles:
        os.remove(file)
    if os.path.isdir(SRC_DIR + '/BUILD_LOG_DIR'):
        shutil.rmtree(SRC_DIR + '/BUILD_LOG_DIR')

    # parallel bld script
    # -------------------
    PBLD_SCRPT = SRC_DIR + '/parallel_build.csh'
    assert os.path.isfile(PBLD_SCRPT), '[%s] does not exist' % PBLD_SCRPT

    sTart = time.time()

    # run parallel build script (submit job)
    # --------------------------------------
    BLD_LOG = open(SRC_DIR + '/log.ParallelInstall', 'w')
    cmd = [PBLD_SCRPT, '-np', '-account', 's1873']
    if GPU: cmd += ['-gpu', '-sand', '-walltime', '02:00:00']
    if PGI: cmd += ['-sand', '-walltime', '02:00:00']
    if DEBUG: cmd += ['-debug']
    #if HOST == 'DISCOVER': 
    #elif HOST=='PLEIADES': 
    #else: 
        #raise Exception('host [%s] not recognized' % HOST)
    run = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)
    output = run.communicate()
    rtrnCode = run.wait()
    if rtrnCode != 0: 
        print('0:'); print(output[0]); print('1:'); print(output[1])
        raise Exception('parallel_build.csh failed')
    BLD_LOG.write('from stdout:\n\n')
    BLD_LOG.write(output[0])
    BLD_LOG.write('\n\nfrom stderr:\n\n')
    BLD_LOG.write(output[1])
    BLD_LOG.close()

    # find JOB_ID from BLD_LOG
    # ------------------------
    JOB_ID = None
    BLD_LOG = open(SRC_DIR + '/log.ParallelInstall', 'r')
    for line in BLD_LOG:
        if 'parallel_build' in line:
            JOB_ID = line.split()[0].strip()
            break
    if (not JOB_ID): raise Exception('Could not find JOB_ID for parallel build')
    BLD_LOG.close()

    # wait for job to finish
    # ----------------------
    while (not job_completed(JOB_ID)):
        time.sleep(30) # seconds

    eNd = time.time()

    writemsg('done. Time taken: %d s.\n\n' % (eNd-sTart), fout)

    # write output of gmh.pl
    # ----------------------
    cmd = 'Config/gmh.pl -Av BUILD_LOG_DIR/LOG'.split()
    sp.check_call(cmd)

    # write output of esma_tgraph.pl
    # ------------------------------
    cmd = 'Config/esma_tgraph.pl -tgfi -n 20 BUILD_LOG_DIR/LOG'.split()
    sp.check_call(cmd)

    # back to CWD
    # -----------
    os.chdir(CWD)

    return True


def build_serial(SRC_DIR, GPU=False, DEBUG=False, fout=None):
    """
    #---------------------------------------------------------------------------
    # def build_serial(SRC_DIR, fout):
    #
    # Build model using the parallel_build.csh script
    #
    # Inputs:
    #  SRC_DIR: source dir
    #     fout: (open) file handle, if None set to sys.stdout
    #
    #---------------------------------------------------------------------------
    """
    
    if not fout: fout = sys.stdout

    # Discover or Pleiades
    # --------------------
    HOST = get_hostname()

    # get current dir and switch to src dir
    # -------------------------------------
    CWD = os.getcwd()
    os.chdir(SRC_DIR)
    
    writemsg(' Building model (serial)...', fout)
    
    # source g5_modules
    # -----------------
    G5_MODULES = SRC_DIR + os.sep + 'g5_modules'
    source_g5_modules(G5_MODULES)

    # set ESMADIR
    # -----------
    os.environ['ESMADIR'] = SRC_DIR + '/..'

    sTart = time.time()
    
    # make install
    # -------------
    BLD_LOG = open(SRC_DIR + '/log.SerialInstall', 'w')
    cmd = []
    cmd += ['make', 'install']
    if GPU: cmd += ['BOPT=GPU']
    if DEBUG: cmd += ['BOPT=g']
    run = sp.Popen(cmd, stdout=BLD_LOG, stderr=BLD_LOG)
    rtrnCode = run.wait()
    if rtrnCode !=0:
        raise Exception('make install failed')
    BLD_LOG.close()
    
    eNd = time.time()

    writemsg('done. Time taken: %d s.\n\n' % (eNd-sTart), fout)

    # write output of gmh.pl
    # ----------------------
    cmd = 'Config/gmh.pl -Av log.SerialInstall'.split()
    sp.check_call(cmd)

    # write output of esma_tgraph.pl
    # ------------------------------
    cmd = 'Config/esma_tgraph.pl -tgfi -n 20 log.SerialInstall'.split()
    sp.check_call(cmd)

    # back to CWD
    # -----------
    os.chdir(CWD)

    return True

def build_pinstall(SRC_DIR, GPU=False, DEBUG=False, fout=None):
    """
    #---------------------------------------------------------------------------
    # def build_pinstall(SRC_DIR, fout):
    #
    # Build model using make with pinstall 
    #
    # Inputs:
    #  SRC_DIR: source dir
    #     fout: (open) file handle, if None set to sys.stdout
    #
    #---------------------------------------------------------------------------
    """
    
    if not fout: fout = sys.stdout

    # Discover or Pleiades
    # --------------------
    HOST = get_hostname()

    # get current dir and switch to src dir
    # -------------------------------------
    CWD = os.getcwd()
    os.chdir(SRC_DIR)
    
    writemsg(' Building model (pinstall)...', fout)
    
    # source g5_modules
    # -----------------
    G5_MODULES = SRC_DIR + os.sep + 'g5_modules'
    source_g5_modules(G5_MODULES)

    # set ESMADIR
    # -----------
    os.environ['ESMADIR'] = SRC_DIR + '/..'

    #print 'ESMADIR: ', os.environ['ESMADIR']
    #print 'ESMA_FC: ', os.environ['ESMA_FC']
    #print 'PGI_LOCALRC: ', os.environ['PGI_LOCALRC']

    #cmd = ['pgfortran', '-show']

    #BLD_LOG = open(SRC_DIR + '/log.pgiconfig', 'w')
    #run = sp.Popen(cmd, stdout=BLD_LOG, stderr=BLD_LOG)
    #rtrnCode = run.wait()
    #if rtrnCode !=0:
        #raise Exception('make install failed')
    #BLD_LOG.close()

    sTart = time.time()
    
    # make install
    # -------------
    BLD_LOG = open(SRC_DIR + '/log.Pinstall', 'w')
    cmd = ['make', '-j8', 'pinstall']
    if GPU: cmd += ['BOPT=GPU']
    if DEBUG: cmd += ['BOPT=g']
    run = sp.Popen(cmd, stdout=BLD_LOG, stderr=BLD_LOG)
    rtrnCode = run.wait()
    if rtrnCode !=0:
        raise Exception('make install failed')
    BLD_LOG.close()
    
    eNd = time.time()

    writemsg('done. Time taken: %d s.\n\n' % (eNd-sTart), fout)

    # write output of gmh.pl
    # ----------------------
    cmd = 'Config/gmh.pl -Av log.Pinstall'.split()
    sp.check_call(cmd)

    # write output of esma_tgraph.pl
    # ------------------------------
    cmd = 'Config/esma_tgraph.pl -tgfi -n 20 log.Pinstall'.split()
    sp.check_call(cmd)

    # back to CWD
    # -----------
    os.chdir(CWD)

    return True

def build_cmake_github(SRC_DIR, DEBUG=False, GNU=False, fout=None):
    """
    #---------------------------------------------------------------------------
    # def build_cmake_developer(SRC_DIR, fout):
    #
    # Build model using make with cmake 
    #
    # Inputs:
    #  SRC_DIR: source dir
    #    DEBUG: build with debugging
    #     fout: (open) file handle, if None set to sys.stdout
    #
    #---------------------------------------------------------------------------
    """
    
    if not fout: fout = sys.stdout

    # Discover or Pleiades
    # --------------------
    HOST = get_hostname()

    # get current dir
    # ---------------
    CWD = os.getcwd()

    # Are we running with Debug or Release?
    # -------------------------------------
    if DEBUG:
        BUILD_TYPE="Debug"
    else:
        BUILD_TYPE="Release"
    BUILD_DIR_NAME='build-'+BUILD_TYPE
    INSTALL_DIR_NAME='install-'+BUILD_TYPE

    BUILD_DIR = os.path.join(SRC_DIR,BUILD_DIR_NAME)
    print("BUILD_DIR: [%s]" % BUILD_DIR)
    mkdir_p(BUILD_DIR)
    os.chdir(BUILD_DIR)
    
    INSTALL_DIR = os.path.join(SRC_DIR,INSTALL_DIR_NAME)
    print("INSTALL_DIR: [%s]" % INSTALL_DIR)

    writemsg(' Building model (cmake - %s)...' % BUILD_TYPE, fout)
    
    # source g5_modules
    # -----------------
    G5_MODULES = SRC_DIR + os.sep + '@env' + os.sep + 'g5_modules'
    #print("G5_MODULES: [%s]" % G5_MODULES)
    source_g5_modules(G5_MODULES)

    # Get BASEDIR
    # -----------
    BASEDIR = os.environ['BASEDIR']
    #print(("BASEDIR: [%s]" % BASEDIR))

    sTart = time.time()

    # Run cmake
    # ---------
    BLD_LOG = open(BUILD_DIR + '/log.cmake', 'w')
    if HOST == 'DISCOVER':
       import platform
       if platform.linux_distribution()[1] == '11':
           CMAKE_EXEC = '/usr/local/other/SLES11.3/cmake/3.14.1/bin/cmake'
       else:
           CMAKE_EXEC = '/usr/local/other/cmake/3.17.0/bin/cmake'
       cmd = [CMAKE_EXEC, SRC_DIR, '-DBASEDIR='+os.path.join(BASEDIR,'Linux')]
    elif HOST=='PLEIADES':
       CMAKE_EXEC = '/nobackup/gmao_SIteam/cmake/cmake-3.14.3/bin/cmake'
       if GNU: 
           cmd = [CMAKE_EXEC, SRC_DIR, '-DBASEDIR='+os.path.join(BASEDIR,'Linux'),'-DCMAKE_Fortran_COMPILER=gfortran','-DCMAKE_C_COMPILER=gcc','-DCMAKE_CXX_COMPILER=g++']
       else:
           cmd = [CMAKE_EXEC, SRC_DIR, '-DBASEDIR='+os.path.join(BASEDIR,'Linux'),'-DCMAKE_Fortran_COMPILER=ifort','-DCMAKE_C_COMPILER=icc','-DCMAKE_CXX_COMPILER=icpc']
    else:
        raise Exception('HOST [%s] not recognized' % HOST)

    cmd.append('-DCMAKE_BUILD_TYPE=%s' % BUILD_TYPE)
    cmd.append('-DCMAKE_INSTALL_PREFIX=%s' % INSTALL_DIR)

    #print(("CMD: [%s]" % cmd))

    run = sp.Popen(cmd, stdout=BLD_LOG, stderr=BLD_LOG)
    rtrnCode = run.wait()
    if rtrnCode !=0:
        raise Exception('cmake failed')
    BLD_LOG.close()
    
    # make install
    # -------------
    BLD_LOG = open(BUILD_DIR + '/log.makeinstall', 'w')

    # MAT We can't do this until discover-cron is SP3 or higher as
    #     it doesn't have libraries needed to link with MPT
    cmd = ['make', '-j6', 'install']

    #build_line = " 'cd %s; source ../src/g5_modules;  make -j6 install'" % BUILD_DIR
    #command_line = "ssh discover17 -t" + build_line
    #cmd = shlex.split(command_line)

    run = sp.Popen(cmd, stdout=BLD_LOG, stderr=BLD_LOG)
    rtrnCode = run.wait()
    if rtrnCode !=0:
        BLD_LOG2 = open(BUILD_DIR + '/log.makeinstall2', 'w')

        run2 = sp.Popen(cmd, stdout=BLD_LOG2, stderr=BLD_LOG2)
        rtrnCode2 = run2.wait()
        if rtrnCode2 != 0:
            raise Exception('make install failed')
        BLD_LOG2.close()
    BLD_LOG.close()
    
    eNd = time.time()

    writemsg('done. Time taken: %d s.\n\n' % (eNd-sTart), fout)

    # back to CWD
    # -----------
    os.chdir(CWD)

    return True

def build_cmaketests(SRC_DIR, DEBUG=False, fout=None):
    """
    #---------------------------------------------------------------------------
    # def build_cmaketests(SRC_DIR, fout):
    #
    # Build cmake tests
    #
    # Inputs:
    #  SRC_DIR: source dir
    #     fout: (open) file handle, if None set to sys.stdout
    #
    #---------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout

    # Discover or Pleiades
    # --------------------
    HOST = get_hostname()

    # get current dir
    # ---------------
    CWD = os.getcwd()

    # Are we running with Debug or Release?
    # -------------------------------------
    if DEBUG:
        BUILD_TYPE="Debug"
    else:
        BUILD_TYPE="Release"
    BUILD_DIR_NAME='build-'+BUILD_TYPE

    # As cmake builds relative to SRC_DIR, use dirname to get that dir
    # ----------------------------------------------------------------
    BUILD_DIR = os.path.join(SRC_DIR,BUILD_DIR_NAME)
    mkdir_p(BUILD_DIR)
    os.chdir(BUILD_DIR)

    writemsg(' Building cmake tests...', fout)
    
    # source g5_modules
    # -----------------
    G5_MODULES = SRC_DIR + os.sep + '@env' + os.sep + 'g5_modules'
    source_g5_modules(G5_MODULES)

    # Get BASEDIR
    # -----------
    BASEDIR = os.environ['BASEDIR']

    # set ESMADIR
    # -----------
    #os.environ['ESMADIR'] = SRC_DIR + '/..'

    sTart = time.time()

    # make tests
    # ----------
    BLD_LOG = open(BUILD_DIR + '/log.maketests', 'w')

    cmd = ['make', 'tests']

    run = sp.Popen(cmd, stdout=BLD_LOG, stderr=BLD_LOG)
    rtrnCode = run.wait()
    if rtrnCode !=0:
        raise Exception('make tests failed')
    BLD_LOG.close()

    eNd = time.time()

    writemsg('done. Time taken: %d s.\n\n' % (eNd-sTart), fout)

    # back to CWD
    # -----------
    os.chdir(CWD)

    return True

def run_cmaketests(SRC_DIR, DEBUG=False, fout=None):
    """
    #---------------------------------------------------------------------------
    # def run_cmaketests(SRC_DIR, fout):
    #
    # Run cmake tests
    #
    # Inputs:
    #  SRC_DIR: source dir
    #     fout: (open) file handle, if None set to sys.stdout
    #
    #---------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout

    # Discover or Pleiades
    # --------------------
    HOST = get_hostname()

    # get current dir
    # ---------------
    CWD = os.getcwd()

    # Are we running with Debug or Release?
    # -------------------------------------
    if DEBUG:
        BUILD_TYPE="Debug"
    else:
        BUILD_TYPE="Release"
    BUILD_DIR_NAME='build-'+BUILD_TYPE

    # As cmake builds relative to SRC_DIR, use dirname to get that dir
    # ----------------------------------------------------------------
    BUILD_DIR = os.path.join(SRC_DIR,BUILD_DIR_NAME)
    mkdir_p(BUILD_DIR)
    os.chdir(BUILD_DIR)
    
    writemsg(' Running cmake tests...', fout)
    
    # source g5_modules
    # -----------------
    G5_MODULES = SRC_DIR + os.sep + '@env' + os.sep + 'g5_modules'
    source_g5_modules(G5_MODULES)

    # Get BASEDIR
    # -----------
    BASEDIR = os.environ['BASEDIR']

    # set ESMADIR
    # -----------
    os.environ['ESMADIR'] = SRC_DIR + '/..'

    sTart = time.time()

    # run tests
    # ---------
    RUN_LOG = open(BUILD_DIR + '/log.runtests', 'w')

    cmd = ['ctest', '-V']

    run = sp.Popen(cmd, stdout=RUN_LOG, stderr=RUN_LOG)
    rtrnCode = run.wait()
    RUN_LOG.close()
    eNd = time.time()

    writemsg('done. Time taken: %d s.\n\n' % (eNd-sTart), fout)

    writemsg('\n',fout)

    with open(BUILD_DIR + '/log.runtests', 'r') as RUN_LOG:
        for line in RUN_LOG:
            writemsg("  %s" % line, fout)

    writemsg('\n',fout)

    if rtrnCode !=0:
        raise Exception('ctest failed')

    # back to CWD
    # -----------
    os.chdir(CWD)

    return True

def check_bld(SRC_DIR, MODTYP, CVS=False, OLDLDAS=False, DEBUG=False, fout=None):
    """
    # --------------------------------------------------------------------------
    # Check if key files exist for the specified build. Return True if the files
    # exist, else return False.
    # --------------------------------------------------------------------------
    """
    if not fout: fout = sys.stdout

    if CVS:
        BIN_DIR = SRC_DIR + '/../Linux/bin'
    else:
        # Are we running with Debug or Release?
        # -------------------------------------
        if DEBUG:
            BUILD_TYPE="Debug"
        else:
            BUILD_TYPE="Release"
        INSTALL_DIR_NAME='install-'+BUILD_TYPE
        BIN_DIR = SRC_DIR + os.sep + INSTALL_DIR_NAME + os.sep + 'bin'

    if MODTYP=='AGCM':
        files2chk = [BIN_DIR + '/GEOSgcm.x', BIN_DIR + '/binarytile.x',
                     BIN_DIR + '/g5_modules']
    elif MODTYP=='ADAS':
        files2chk = [BIN_DIR + '/GEOSgcm.x',     BIN_DIR + '/GSIsa.x',
                     BIN_DIR + '/oiqcbufr.x',    BIN_DIR + '/mkiau.x',
                     BIN_DIR + '/GEOSgcmPert.x', BIN_DIR + '/mkiau.x',
                     BIN_DIR + '/g5_modules']
    elif MODTYP=='LDAS':
        if OLDLDAS:
           files2chk = [BIN_DIR + '/LDASsa_mpi.x',
                        BIN_DIR + '/LDASsa_assim_mpi.x']
        else:
           files2chk = [BIN_DIR + '/GEOSldas.x']
    else:
        raise Exception('MODTYPE [%s] not recognized!' % MODTYP)

    for file in files2chk:
        if not os.path.isfile(file):
            writemsg('check_bld: file [%s] does not exist!\n' % file, fout)
            return False

    return True

def build_doc(SRC_DIR, MODTYP, fout=None):
    """
    #---------------------------------------------------------------------------
    # def build_doc(SRC_DIR, fout):
    #
    # Build model documentation
    #
    # Inputs:
    #  SRC_DIR: source dir
    #     fout: (open) file handle, if None set to sys.stdout
    #
    #---------------------------------------------------------------------------
    """
    
    if not fout: fout = sys.stdout

    # Discover or Pleiades
    # --------------------
    HOST = get_hostname()

    # get current dir and switch to src dir
    # -------------------------------------
    CWD = os.getcwd()
    os.chdir(SRC_DIR)
    
    writemsg(' Building documentation...', fout)
    
    # source g5_modules
    # -----------------
    G5_MODULES = SRC_DIR + os.sep + 'g5_modules'
    source_g5_modules(G5_MODULES)

    # set ESMADIR
    # -----------
    os.environ['ESMADIR'] = SRC_DIR + '/..'

    sTart = time.time()
    
    # make install
    # -------------
    BLD_LOG = open(SRC_DIR + '/log.DocBuild', 'w')
    cmd = []
    cmd += ['make', 'doc']
    run = sp.Popen(cmd, stdout=BLD_LOG, stderr=BLD_LOG)
    rtrnCode = run.wait()
    if rtrnCode !=0:
        raise Exception('make doc failed')
    BLD_LOG.close()
    
    eNd = time.time()

    writemsg('done. Time taken: %d s.\n\n' % (eNd-sTart), fout)

    # back to CWD
    # -----------
    os.chdir(CWD)

    return True


def check_doc(SRC_DIR, MODTYP, fout=None):
    """
    # --------------------------------------------------------------------------
    # Check if key files exist for the specified build. Return True if the files
    # exist, else return False.
    # --------------------------------------------------------------------------
    """
    if not fout: fout = sys.stdout

    DOC_DIR = SRC_DIR + '/../Linux/doc'

    if MODTYP=='AGCM':
        files2chk = [DOC_DIR + '/GCM_doc.pdf', DOC_DIR + '/MAPL_UsersGuide.pdf']
    else:
        raise Exception('MODTYPE [%s] not recognized!' % MODTYP)

    for file in files2chk:
        if not os.path.isfile(file):
            writemsg('check_doc: file [%s] does not exist!\n' % file, fout)
            return False

    return True



def submit_job(JOB_SCRPT, account=None, qdbg=None, fout=None):
    """
    # --------------------------------------------------------------------------
    # Submit job to PBS queue, wait for job to complete and print CPU and Wall
    # times from PBS output
    #
    # Input:
    #    JOB_SCRPT: job script to submit
    #         fout: open output file handle, if None set to sys.stdout
    # --------------------------------------------------------------------------
    """

    #print 'JOB_SCRPT:', JOB_SCRPT

    HOST = get_hostname()
    if not fout: fout = sys.stdout
    if not os.path.isfile(JOB_SCRPT):
        raise Exception('job script [%s] does not exist' % JOB_SCRPT)

    _account =''
    if account is not None:
        if HOST == 'DISCOVER':
            _account= '--account='+account

    # current dir and job dir
    # -----------------------
    CWD = os.getcwd()
    JOB_DIR = os.path.dirname(os.path.abspath(JOB_SCRPT))
    JOB_NAME = JOB_DIR.split(os.sep)[-1]

    # submit job from the dir containing job_scrpt
    # --------------------------------------------
    os.chdir(JOB_DIR)
    writemsg(' Submitting job...', fout)
    if HOST == 'DISCOVER':
        if qdbg:
            cmd = ['sbatch',_account, '--qos=debug', '--time=1:00:00', JOB_SCRPT]
            #cmd = ['sbatch', '--time=1:00:00', JOB_SCRPT]
        else:
            cmd = ['sbatch',_account, JOB_SCRPT]
    elif HOST=='PLEIADES':
        if qdbg:
            cmd = ['qsub', '-q', 'devel', '-l', 'walltime=1:00:00', JOB_SCRPT]
            #cmd = ['qsub', '-l', 'walltime=2:00:00', JOB_SCRPT]
        else:
            cmd = ['qsub', JOB_SCRPT]
    else: 
        raise Exception('HOST [%s] not recognized' % HOST)
    #print 'cmd:', ' '.join(cmd)
    run = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)
    output = run.communicate()
    rtrnCode = run.wait()
    if rtrnCode !=0:
        print('0:'); print(output[0]); print('1:'); print(output[1])
        raise Exception('qsub [%s] failed' % JOB_SCRPT.split(os.sep)[-1])
    JOB_ID = output[0].split()[-1].strip()
    tstart = datetime.now().strftime('%Y/%m/%d, %H:%M:%S')
    writemsg('done. [%s, %s]\n' % (JOB_ID, tstart), fout)
    os.chdir(CWD)

    # wait for job to complete
    # ------------------------
    writemsg(' Waiting for job to complete...', fout)
    while (not job_completed(JOB_ID)):
        time.sleep(30) # seconds
    tend = datetime.now().strftime('%Y/%m/%d, %H:%M:%S')
    writemsg('completed. [%s]\n' % tend, fout)

#     PBSOutput = glob.glob(JOB_DIR + '/*.o' + JobNum_RUN.split('.')[0])[0]

#     # print CPU and Wall times from PBS output
#     # ----------------------------------------
#     WallTime = ''
#     CPUTime = ''
#     fin = open(PBSOutput, 'r')
#     for line in fin:
#         if 'Walltime Used' in line:
#             [hh, mm, ss] = line.strip().split(' :')[-1].split(':')[0:3]
#             WallTime = str(float(hh)*3600+float(mm)*60+float(ss))
#         if 'CPU Time Used' in line:
#             [hh, mm, ss] = line.strip().split(' :')[-1].split(':')[0:3]
#             CPUTime = str(float(hh)*3600+float(mm)*60+float(ss))
#     fin.close()
#     if not WallTime: WallTime = 'not found'
#     if not CPUTime: CPUTime = 'not found'
#     writemsg('%s %s s.\n' % (('['+JOB_NAME+'] Wall time:').rjust(30), WallTime), fout)
#     writemsg('%s %s s.\n' % (('['+JOB_NAME+'] CPU time:').rjust(30), CPUTime), fout)



def egress_exists(EGRESS_PATH):
    """
    # --------------------------------------------------------------------------
    # Check EGRESS for successful job completion
    #
    # Input:
    #    EGRESS_PATH: path to file EGRESS
    # Output:
    #    True/False
    # --------------------------------------------------------------------------
    """
       
    if os.path.isfile(EGRESS_PATH):        
        return True
    else:
        return False



def create_setup_input(setup_opts, setup_file, fout=None):
    """
    # --------------------------------------------------------------------------
    # Write input file for gcm_setup. It is the caller's responsibility to
    # ensure that setup_opts is an instance of collections.OrderedDict
    #
    # Input:
    #     setup_opts: an OrderedDict of options
    #     setup_file: file to write setup options to
    # --------------------------------------------------------------------------
    """
    
    if not fout: fout = sys.stdout
    
    writemsg(' Creating input file for exp setup script...', fout)

    sout = open(setup_file, 'w')
    for key in setup_opts.keys():
        sout.write('%s = %s\n' % (key, setup_opts[key]))
    sout.close()

    writemsg('done.\n', fout)
    


def get_file_contents():
    """
    #---------------------------------------------------------------------------
    # Return the contents of the files $HOME/EXPDIRroot, $HOME/HOMDIRroot,
    # $HOME/.GROUProot and $HOME/.HISTORYrc. This should be done prior to
    # running gcm_setup (in setup_experiment)
    #---------------------------------------------------------------------------
    """

    # cache $HOME/EXPDIRroot, $HOME/HOMDIRroot, $HOME/.GROUProot
    # ----------------------------------------------------------
    ## filenames
    expname = os.environ['HOME'] + '/.EXPDIRroot'
    homname = os.environ['HOME'] + '/.HOMDIRroot'
    grpname = os.environ['HOME'] + '/.GROUProot'
    hstname = os.environ['HOME'] + '/.HISTORYrc'

    ## exp
    if os.path.isfile(expname):
        expfile = open(expname)
        exp_content = expfile.read()
        expfile.close()
    else:
        exp_content = ''

    ## hom
    if os.path.isfile(homname):
        homfile = open(homname)
        hom_content = homfile.read()
        homfile.close()
    else:
        hom_content = ''

    ## grp
    if os.path.isfile(grpname):
        grpfile = open(grpname)
        grp_content = grpfile.read()
        grpfile.close()
    else:
        grp_content = ''

    ## hst
    if os.path.isfile(hstname):
        hstfile = open(hstname)
        hst_content = hstfile.read()
        hstfile.close()
    else:
        hst_content = ''

    return [exp_content, hom_content, grp_content, hst_content]



def write_file_contents(exp_content, hom_content, grp_content, hst_content):
    """
    #--------------------------------------------------------------------------
    # Write the cached contents of the files $HOME/EXPDIRroot, $HOME/HOMDIRroot,
    # $HOME/.GROUProot and $HOME/.HISTORYrc back to these files. This should be
    # after running gcm_setup (in setup_experiment)
    #--------------------------------------------------------------------------
    """

    ## filenames
    expname = os.environ['HOME'] + '/.EXPDIRroot'
    homname = os.environ['HOME'] + '/.HOMDIRroot'
    grpname = os.environ['HOME'] + '/.GROUProot'
    hstname = os.environ['HOME'] + '/.HISTORYrc'

    ## exp
    if os.path.isfile(expname):
        expfile = open(expname, 'w')
        expfile.write(exp_content)
        expfile.close()
    ## hom
    if os.path.isfile(homname):
        homfile = open(homname, 'w')
        homfile.write(hom_content)
        homfile.close()
    ## grp
    if os.path.isfile(grpname):
        grpfile = open(grpname, 'w')
        grpfile.write(grp_content)
        grpfile.close()
    ## hst
    if os.path.isfile(hstname):
        hstfile = open(hstname, 'w')
        hstfile.write(hst_content)
        hstfile.close()



def run_setup_script(SETUP_SCRPT, SETUP_INPUT, GPU=False, fout=None, quiet=None, LINK=False):
    """
    # --------------------------------------------------------------------------
    # ./gcm_setup: awk 'BEGIN {FS="="}{print $2}' GCM_INPUT | csh GCM_SETUP
    # --------------------------------------------------------------------------
    """    

    if not fout: fout = sys.stdout
    
    APP_DIR = os.path.dirname(os.path.abspath(SETUP_SCRPT))
    CWD = os.getcwd()
    os.chdir(APP_DIR)

    writemsg(' Running %s...' % SETUP_SCRPT.split(os.sep)[-1], fout, quiet)
    cmd1 = ['awk', 'BEGIN {FS="="}{print $2}', SETUP_INPUT]
    cmd2 = ['csh', SETUP_SCRPT]
    # MAT: Do not do the cvs checkout due to inode pressure
    cmd2 += ['--nocvs']
    if GPU: cmd2 += ['-g']
    if LINK: cmd2 += ['--link']
    run1 = sp.Popen(cmd1, stdout=sp.PIPE, stderr=sp.PIPE)
    rtrnCode = run1.wait()
    if rtrnCode != 0: raise Exception('run1 (awk) failed')
    run2 = sp.Popen(cmd2, stdin=run1.stdout,stdout=sp.PIPE)
    rtrnCode = run2.wait()
    if rtrnCode != 0: raise Exception('run2 (SETUP_SCRPT) failed')
    run1.stdout.close()
    output = run2.communicate()
    if output[1]:
        print('0:'); print(output[0]); print('1:'); print(output[1])
        raise Exception('utils:run_setup_script - something wrong')
    writemsg('done.\n', fout, quiet)

    os.chdir(CWD)


def copy_rst(SRC, DEST, fout=None):
    """
    # --------------------------------------------------------------------------
    # Copy restarts from SRC dir to DEST dir
    # --------------------------------------------------------------------------
    """
    
    if not fout: fout = sys.stdout

    writemsg(' Copying restarts from [%s]...' % SRC, fout)

    if not os.path.isdir(SRC):
        raise Exception('could not find [%s] for rst files' % SRC)
    if not os.path.isfile(SRC + '/cap_restart'):
        raise Exception('cap_restart not found in [%s]' % SRC)
    rstFiles = glob.glob(SRC + '/*_rst')
    if len(rstFiles)==0:
        raise Exception('restart files not found in [%s]' % SRC)
    rstFiles.append(SRC + '/cap_restart')
    for rstfile in rstFiles:
        shutil.copy(rstfile, DEST)

    # make these files readable
    MY_RST_FILES = glob.glob(DEST + '/*_rst')
    MY_RST_FILES.append(DEST + '/cap_restart')
    for rstfile in MY_RST_FILES:
        assert(os.path.isfile(rstfile))
        os.chmod(rstfile, 0o644)

    writemsg('done.\n', fout)



def edit_cap_rc_gcm_run_j(RUN_DIR, howlong, timer=False, memusage=False, PGI=False, LOGGING=False, fout=None):
    """
    # --------------------------------------------------------------------------
    # Edit CAP.rc to run an experiment for the given length of time. Also turn
    # on MAPL_Timers and MAPL_MemUtils if asked to.
    #
    # Inputs:
    #     RUN_DIR: where CAP.rc and gcm_run.j reside
    #     howlong: run duration
    #       timer: if True, turn on MAPL_Timers
    #    memusage: if True, turn on MAPL_MemUtils
    #         PGI: if True, turn on run 12 cores per node
    #     LOGGING: if True, turn on ESMF logging
    #        fout: handle of open output file, if None - set to sys.stdout
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout

    writemsg(' Editing CAP.rc and gcm_run.j for [%s] run...' % howlong, fout)

    CAP_RC = RUN_DIR + '/CAP.rc'; assert os.path.isfile(CAP_RC)
    GCM_RUN_J = RUN_DIR + '/gcm_run.j'; assert os.path.isfile(GCM_RUN_J)

    # find time step
    # --------------
    if howlong=='1step':
        TimeStep = None
        fin = open(CAP_RC)
        for line in fin:
            if 'HEARTBEAT_DT' in line:
                TimeStep = line.split(':')[1].strip()
        if not TimeStep:
            raise Exception('HEARTBEAT_DT not found in [%s]' % CAP_RC)
        fin.close()
        TimeStep = int(TimeStep)/60

    # edit CAP.rc
    # -----------
    if   howlong=='1day':  job_sgmt = 'JOB_SGMT:     00000001 000000\n'
    elif howlong=='1week': job_sgmt = 'JOB_SGMT:     00000007 000000\n'
    elif howlong=='1step': job_sgmt = 'JOB_SGMT:     00000000 00%02d00\n' % TimeStep
    else:
        raise Exception('unknown duration [%s]: can be one of 1step/1day/1week' % howlong)
    fin = open(CAP_RC, 'r'); lines = fin.readlines(); fin.close()
    cout = open(CAP_RC, 'w')
    for line in lines:
        if 'JOB_SGMT:' in line:
            line = job_sgmt
        if 'NUM_SGMT:' in line:
            line = 'NUM_SGMT:     1\n'
        if timer:
            if 'MAPL_ENABLE_TIMERS:' in line:
                line = 'MAPL_ENABLE_TIMERS: YES\n'
        if memusage:
            if 'MAPL_ENABLE_MEMUTILS:' in line:
                line = 'MAPL_ENABLE_MEMUTILS: YES\nMAPL_MEMUTILS_MODE: 1\n'
        cout.write(line)
    cout.close()

    # edit gcm_run.j
    # --------------
    fin = open(GCM_RUN_J, 'r'); lines = fin.readlines(); fin.close()
    gout = open(GCM_RUN_J, 'w')
    for line in lines:
        if 'qsub' in line:
            line = '# ' + line
        if 'sbatch' in line:
            line = '# ' + line
        if '#PBS -l walltime' in line:
            line = line.replace('12','1')
            line = line.replace('8','1')
        if '#SBATCH --time' in line:
            line = line.replace('12','1')
            line = line.replace('8','1')
        # For now, always run on the Haswell, otherwise Intel 16+ will
        #   throw failures due to differences in architecture
        #   NOTE: that at NAS we run on a single chipset no matter what
        if '#SBATCH --constraint' in line:
            line = line.replace('sp3','hasw')

        if LOGGING:
            if "$RUN_CMD $NPES ./GEOSgcm.x" in line:
                line = line.replace('GEOSgcm.x','GEOSgcm.x --esmf_logtype multi_on_error')

        # Current PGI + Open MPI seems to have a limit of 12 cores per node
        if PGI:
            if "select=4" in line:
                line = line.replace('select=4','select=8')
                line = line.replace('ncpus=24','ncpus=12')
                line = line.replace('mpiprocs=24','mpiprocs=12')

        gout.write(line);

        if PGI:
            if "#SBATCH --ntasks" in line:
                gout.write("#SBATCH --ntasks-per-node=12\n")

    gout.close()    

    writemsg('done.\n', fout)



def bootstrapAGCM(RUN_DIR, fout=None):
    """
    # --------------------------------------------------------------------------
    # Edit AGCM.rc to allow bootstrapping
    #
    # Input:
    #         RUN_DIR: where AGCM.rc resides
    #            fout: handle of open output file, if None - set to sys.stdout
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout
    
    writemsg(' Turning on MAPL Bootstrapping...', fout)

    # first ensure the rst files have been copied over
    assert(os.path.isfile(RUN_DIR+'/cap_restart'))
    assert(os.path.isfile(RUN_DIR+'/fvcore_internal_rst'))

    # remove gocart_internal_rst
    GOCART_INT_RST = RUN_DIR+'/gocart_internal_rst'
    if os.path.isfile(GOCART_INT_RST): 
        writemsg(' This script assumes GOCART will be bootstrapped. So we remove GOCART INTERNAL restart...', fout)
        os.remove(GOCART_INT_RST)

    # now, edit AGCM.rc
    AGCM_RC = os.path.join(RUN_DIR,'AGCM.rc'); assert os.path.isfile(AGCM_RC)
    fin = open(AGCM_RC, 'r'); lines = fin.readlines(); fin.close()
    gout = open(AGCM_RC, 'w')
    for line in lines:
        if ('MAPL_ENABLE_BOOTSTRAP' in line) and ('YES' not in line):
            line = line.replace('NO', 'YES')
        gout.write(line);
    gout.close()
    writemsg('done.\n', fout)


    
def useSatsim(RUN_DIR, fout=None):
    """
    # --------------------------------------------------------------------------
    # Edit AGCM.rc, HISTORY.rc to run with SATSIM GridComp
    #
    # Input:
    #         RUN_DIR: where AGCM.rc and HISTORY.rc reside
    #            fout: handle of open output file, if None - set to sys.stdout
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout
    
    writemsg(' Editing to run with SATSIM...', fout)

    # edit AGCM.rc
    # ------------
    AGCM_RC = RUN_DIR + '/AGCM.rc'; assert os.path.isfile(AGCM_RC)
    fin = open(AGCM_RC, 'r'); lines = fin.readlines(); fin.close()
    sout = open(AGCM_RC, 'w')
    for line in lines:
        if ('USE_SATSIM' in line):
            line = line.replace('0', '1')
        sout.write(line)
    sout.close()

    # edit HISTORY.rc
    # add the variable TCLISCCP to geosgcm_prog
    HIST_RC = RUN_DIR + '/HISTORY.rc'; assert os.path.isfile(HIST_RC)
    fin = open(HIST_RC, 'r'); lines = fin.readlines(); fin.close()
    gout = open(HIST_RC, 'w')
    FOUND = False
    inBlock = False
    for line in lines:
        if 'geosgcm_prog.fields:' in line:
            FOUND = True
            inBlock = True
        if (inBlock) and ('::' in line):
            line = "'TCLISCCP', 'SATSIM',\n" + line
            inBlock = False
        gout.write(line)
            
    if not FOUND:
        raise Exception('geosgcm_prog.fields not found in HISTORY.rc')

    gout.close()

    writemsg('done.\n', fout)

def useReplay(RUN_DIR, noIncrements=False, fout=None):
    """
    # --------------------------------------------------------------------------
    # Edit AGCM.rc to use regular replay
    #
    # Input:
    #         RUN_DIR: where AGCM.rc resides
    #            fout: handle of open output file, if None - set to sys.stdout
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout

    HOST = get_hostname()
    
    writemsg(' Editing to run with Regular Replay...', fout)

    # edit AGCM.rc
    # ------------
    AGCM_RC = RUN_DIR + '/AGCM.rc'; assert os.path.isfile(AGCM_RC)
    fin = open(AGCM_RC, 'r'); lines = fin.readlines(); fin.close()
    sout = open(AGCM_RC, 'w')
    for line in lines:
        if ('#M2' in line):
            line = line.replace('#M2', '   ')
        if ('verification' in line):
            if HOST=='PLEIADES':
                line = line.replace('/discover/nobackup/projects/gmao/share/gmao_ops','/nobackup/gmao_SIteam/ModelData')
        if noIncrements:
            if (re.match('^# *REPLAY_P:',line)):
                line = ('    REPLAY_P: NO\n')
            if (re.match('^# *REPLAY_U:',line)):
                line = ('    REPLAY_U: NO\n')
            if (re.match('^# *REPLAY_V:',line)):
                line = ('    REPLAY_V: NO\n')
            if (re.match('^# *REPLAY_T:',line)):
                line = ('    REPLAY_T: NO\n')
            if (re.match('^# *REPLAY_QV:',line)):
                line = ('    REPLAY_QV: NO\n')
            if (re.match('^# *REPLAY_O3:',line)):
                line = ('    REPLAY_O3: NO\n')
            if (re.match('^# *REPLAY_TS:',line)):
                line = ('    REPLAY_TS: NO\n')
        sout.write(line)
    sout.close()

    writemsg('done.\n', fout)

def useDasmode(RUN_DIR, fout=None):
    """
    # --------------------------------------------------------------------------
    # Edit AGCM.rc to use Dasmode
    #
    # Input:
    #         RUN_DIR: where AGCM.rc resides
    #            fout: handle of open output file, if None - set to sys.stdout
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout

    HOST = get_hostname()
    
    writemsg(' Editing to run with Dasmode...', fout)

    # edit AGCM.rc
    # ------------
    AGCM_RC = RUN_DIR + '/AGCM.rc'; assert os.path.isfile(AGCM_RC)
    fin = open(AGCM_RC, 'r'); lines = fin.readlines(); fin.close()
    sout = open(AGCM_RC, 'w')
    for line in lines:
        if ('AGCM_IMPORT_RESTART_FILE:' in line):
            line = line.replace('#', ' ')
        sout.write(line)
    sout.close()

    writemsg('done.\n', fout)



def rst_bin2nc4(RUN_DIR, fout=None):    
    """
    # --------------------------------------------------------------------------
    # Edit AGCM.rc to set restart/checkpoint type to nc4
    #
    # Input:
    #         RUN_DIR: where AGCM.rc resides
    #            fout: handle of open output file, if None - set to sys.stdout
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout
    
    writemsg(' Setting rst/chkpt file type to pnc4...', fout)

    # edit AGCM.rc
    # ------------
    AGCM_RC = RUN_DIR + '/AGCM.rc'; assert os.path.isfile(AGCM_RC)
    fin = open(AGCM_RC, 'r'); lines = fin.readlines(); fin.close()
    rout = open(AGCM_RC, 'w')
    for line in lines:
        # order of replacement is important
        # first replace pbinary with pnc4 and
        # then binary with nc4
        if 'VEGDYN' not in line:
            line = line.replace('pbinary', 'pnc4')
            line = line.replace('binary', 'pnc4')
        rout.write(line);
        if 'VEGDYN' not in line:
            if 'DYN_INTERNAL_RESTART_FILE' in line:
                rout.write('DYN_INTERNAL_RESTART_TYPE: pnc4\n')
            if 'DYN_INTERNAL_CHECKPOINT_FILE' in line:
                rout.write('DYN_INTERNAL_CHECKPOINT_TYPE: pnc4\n')            
    rout.close()
    writemsg('done.\n', fout)



# def edit_agcm_rc(RUN_DIR, nc4_rst=False, bootstrapGocart=False, useSatsim=False, num_rd_wrt=0, fout=None):
#     """
#     # --------------------------------------------------------------------------
#     # Edit AGCM.rc to 
#     #    set NUM_READERS and NUM_WRITERS to 1. needed to run gcm_regress.j
#     #    set restart/checkpoint type to nc4
#     #    bootstrap GOCART
#     #
#     # Input:
#     #         RUN_DIR: where CAP.rc and gcm_run.j reside
#     #         nc4_rst: if True, set restart/checkpoint file types to pnc4
#     # bootstrapGocart: if True, bootstrap gocart rst files
#     #       useSatsim: if True, run with SATSIM GridComp
#     #      num_rd_wrt: if 1 set NUM_READER = NUM_WRITERS = 1, else do nothing
#     #            fout: handle of open output file, if None - set to sys.stdout
#     # --------------------------------------------------------------------------
#     """

#     if not fout: fout = sys.stdout
    
#     writemsg(' Editing AGCM.rc:\n', fout)

#     # copy AGCM.rc to AGCM.rc.orig
#     # ----------------------------
#     AGCM_RC = RUN_DIR + '/AGCM.rc'; assert os.path.isfile(AGCM_RC)
#     AGCM_RC_ORIG = RUN_DIR + '/AGCM.rc.orig'
#     if not os.path.isfile(AGCM_RC_ORIG):
#         shutil.copy(AGCM_RC, AGCM_RC_ORIG)

#     # set NUM_READERS = NUM_WRITERS = 1
#     # ---------------------------------
#     if num_rd_wrt==1:
#         writemsg('    setting NUM_READERS and NUM_WRITERS to 1...', fout)
#         fin = open(AGCM_RC, 'r'); lines = fin.readlines(); fin.close()
#         aout = open(AGCM_RC, 'w')
#         for line in lines:
#             if 'NUM_READERS:' in line:
#                 line = 'NUM_READERS: 1\n'
#             if 'NUM_WRITERS:' in line:
#                 line = 'NUM_WRITERS: 1\n'
#             aout.write(line);
#         aout.close()
#         writemsg('done.\n', fout)

#     # bootstrap gocart
#     # ----------------
#     if bootstrapGocart:
#         writemsg('    bootstrapping GOCART...', fout)
#         # first ensure the rst files have been copied over
#         assert(os.path.isfile(RUN_DIR+'/cap_restart'))
#         assert(os.path.isfile(RUN_DIR+'/fvcore_internal_rst'))
#         GOCART_INT_RST = RUN_DIR+'/gocart_internal_rst'
#         if os.path.isfile(GOCART_INT_RST):
#             os.remove(GOCART_INT_RST)

#         fin = open(AGCM_RC, 'r'); lines = fin.readlines(); fin.close()
#         aout = open(AGCM_RC, 'w')
#         for line in lines:
#             if ('gocart_internal_rst' in line) and ('-gocart_internal_rst' not in line):
#                 line = line.replace('gocart_internal_rst', '-gocart_internal_rst')
#             aout.write(line);
#         aout.close()
#         writemsg('done.\n', fout)

#     # run w/ SATSIM GridComp
#     # ----------------------
#     if useSatsim:
#         writemsg('    setting SATSIM flags...', fout)
#         fin = open(AGCM_RC, 'r'); lines = fin.readlines(); fin.close()
#         sout = open(AGCM_RC, 'w')
#         for line in lines:
#             if ('USE_SATSIM' in line):
#                 line = line.replace('0', '1')
#             sout.write(line)
#         sout.close()
#         writemsg('done.\n', fout)

#     # set restart/checkpoint file type to parallel netCDF4
#     # ----------------------------------------------------
#     if nc4_rst:
#         writemsg('    setting restart/checkpoint file type to pnc4...', fout)
#         fin = open(AGCM_RC, 'r'); lines = fin.readlines(); fin.close()
#         aout = open(AGCM_RC, 'w')
#         for line in lines:
#             # order of replacement is important
#             # first replace pbinary with pnc4 and
#             # then binary with nc4
#             if 'VEGDYN' not in line:
#                 line = line.replace('pbinary', 'pnc4')
#                 line = line.replace('binary', 'pnc4')
#             aout.write(line);
#             if 'VEGDYN' not in line:
#                 if 'DYN_INTERNAL_RESTART_FILE' in line:
#                     aout.write('DYN_INTERNAL_RESTART_TYPE: pnc4\n')
#                 if 'DYN_INTERNAL_CHECKPOINT_FILE' in line:
#                     aout.write('DYN_INTERNAL_CHECKPOINT_TYPE: pnc4\n')            
#         aout.close()
#         writemsg('done.\n', fout)
        


def edit_gcm_regress_j(RUN_DIR, USE_REPLAY, resolution, PGI=False, nc4_rst=False, fout=None):
    """
    # --------------------------------------------------------------------------
    # Edit gcm_regress.j to
    #    correctly compare nc4 checkpoint files (cdo instead of cmp)
    #
    # Input:
    #     RUN_DIR: gcm_regress.j is in RUN_DIR/regress/
    #     nc4_rst: use cdo to compare (instead to cmp)
    #  num_rd_wrt: if 1 set NUM_READER = NUM_WRITERS = 1, else do nothing
    #        fout: handle of open output file, if None - set to sys.stdout
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout
    
    #if nc4_rst:
        #writemsg(' Editing gcm_regress.j (replacing cmp with cdo)...', fout)

        ## copy gcm_regress.j to gcm_regress.j.orig
        ## ----------------------------------------
        #GCM_REGRESS_J = RUN_DIR + '/regress/gcm_regress.j'; assert os.path.isfile(GCM_REGRESS_J)
        #GCM_REGRESS_J_ORIG = RUN_DIR + '/regress/gcm_regress.j.orig'
        #if not os.path.isfile(GCM_REGRESS_J_ORIG):
            #shutil.copy(GCM_REGRESS_J, GCM_REGRESS_J_ORIG)

        #fin = open(GCM_REGRESS_J, 'r'); lines = fin.readlines(); fin.close()
        #gout = open(GCM_REGRESS_J, 'w')
        #for line in lines:
            #line = line.replace('cmp', 'cdo -s diffn')
            #gout.write(line);
        #gout.close()
        #writemsg('done.\n', fout)

    writemsg(' Editing %s gcm_regress.j (editing wall time)...' % resolution, fout)

    # copy gcm_regress.j to gcm_regress.j.orig
    # ----------------------------------------
    GCM_REGRESS_J = RUN_DIR + '/regress/gcm_regress.j'; assert os.path.isfile(GCM_REGRESS_J)
    GCM_REGRESS_J_ORIG = RUN_DIR + '/regress/gcm_regress.j.orig'
    if not os.path.isfile(GCM_REGRESS_J_ORIG):
        shutil.copy(GCM_REGRESS_J, GCM_REGRESS_J_ORIG)

    fin = open(GCM_REGRESS_J, 'r'); lines = fin.readlines(); fin.close()
    gout = open(GCM_REGRESS_J, 'w')
    for line in lines:
        if '#PBS -l walltime' in line:
            line = line.replace('12','1')
            line = line.replace('8','1')
        if '#SBATCH --time' in line:
            line = line.replace('12','1')
            line = line.replace('8','1')

        # Current PGI + Open MPI seems to have a limit of 12 cores per node
        if PGI:
            if "select=4" in line:
                line = line.replace('select=4','select=12')
                line = line.replace('ncpus=24','ncpus=8')
                line = line.replace('mpiprocs=24','mpiprocs=8')
        gout.write(line);
        if PGI:
            if "#SBATCH --ntasks" in line:
                gout.write("#SBATCH --ntasks-per-node=8\n")
    gout.close()
    writemsg('done.\n', fout)


def edit_co2_gridcomp_rc(RUN_DIR, fout=None):
    """
    # --------------------------------------------------------------------------
    # for Ganymed-2_1_p1, if running with GOCART 
    # set CMS_EMIS to 0 in CO2_GridComp.rc
    #
    # Input:
    #     RUN_DIR: where CAP.rc and gcm_run.j reside
    #        fout: handle of open output file, if None - set to sys.stdout
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout

    writemsg(' Setting CMS_EMIS to 0...', fout)

    CO2_GRIDCOMP_RC = RUN_DIR + '/RC/CO2_GridComp.rc'
    assert os.path.isfile(CO2_GRIDCOMP_RC)

    fin = open(CO2_GRIDCOMP_RC, 'r'); lines = fin.readlines(); fin.close()
    cout = open(CO2_GRIDCOMP_RC, 'w')
    ALREADY_SET = False
    for line in lines:
        if 'CMS_EMIS:' in line:
            if line.split(':')[-1].strip()=='0': 
                ALREADY_SET = True
            else: 
                line = 'CMS_EMIS: 0\n'
        cout.write(line);
    cout.close()

    if ALREADY_SET: writemsg('already set.\n', fout)
    else: writemsg('done.\n', fout)



def check_lt_test(REGRESS_DIR, resolution, fout=None):
    """
    # ------------------------------------------------------------
    # def check_lt_test(REGRESS_DIR):
    #
    # count and return successes for GCM layout/transparency test
    #
    # Inputs:
    #    REGRESS_DIR: directory containing gcm_regress and the
    #                 corresponding output file
    #     resolution: string with resolution
    #           fout: handle of open output file, if None,
    #                 set to sys.stdout
    # Output:
    #    Return True/False
    # ------------------------------------------------------------
    """

    if not fout: fout = sys.stdout

    HOST = get_hostname()

    LT_PASSED = True

    writemsg(' Successes at %s for layout/transparency test...' % resolution, fout)
    
    if HOST == 'DISCOVER':
        RGRS_OUT = glob.glob(REGRESS_DIR+'/slurm*')
    elif HOST=='PLEIADES':
        RGRS_OUT = glob.glob(REGRESS_DIR+'/*_RGRS.o*')

    if len(RGRS_OUT)==0:
        writemsg('\n NOT run!\n', fout)
    else:
        assert len(RGRS_OUT) == 1, "0 or multiple job_out files in LOG_DIR??"
        fin_content = open(RGRS_OUT[0]).read()
        numSuccesses = len(fin_content.split('Success!')) - 1
        numFailures  = len(fin_content.split('Failed!'))  - 1
        NUM_TESTS = numSuccesses + numFailures
        writemsg('[%s/%s]...' % (numSuccesses, NUM_TESTS), fout)
        if NUM_TESTS != 0 and numSuccesses == NUM_TESTS:
            writemsg('PASSED.\n', fout)
        else:
            LT_PASSED = False
            writemsg('FAILED.\n', fout)

    return LT_PASSED



def createDirs(HOM_DIR, EXSTNG_BLD, fout=None):
    """
    # ------------------------------------------------------------
    # def createDirs(HOM_DIR, EXSTNG_BLD, fout=None):
    #
    # create run directory and link to specified build dir
    # under experiment home dir
    #
    # Inputs:
    #        HOM_DIR: directory that will contain bld/, run/
    #     EXSTNG_BLD: build dir containing src/, Linux/ etc.
    #           fout: handle of open output file, if None,
    #                 set to sys.stdout
    #
    # ------------------------------------------------------------
    """

    if not fout: fout = sys.stdout

    writemsg('\n', fout)

    BLD_DIR = HOM_DIR + '/bld'
    RUN_DIR = HOM_DIR + '/run'

    # quit if one of BLD_DIR, RUN_DIR exists
    # --------------------------------------
    __QUIT__ = False
    if os.path.isdir(RUN_DIR):
        writemsg(' run dir [%s] already exists!\n' % RUN_DIR)
        __QUIT__ = True
    if os.path.islink(BLD_DIR):
        writemsg(' link to [%s] already exists!\n' % EXSTNG_BLD)
        __QUIT__ = True
    if __QUIT__:
        sys.exit(-1)

    # create run dir and link to bld dir
    # ----------------------------------
    mkdir_p(RUN_DIR)
    writemsg(' Creating link to specified bld...', fout)
    create_link(EXSTNG_BLD, HOM_DIR, 'bld')
    writemsg('done.\n', fout)

    # print dir names
    # ---------------
    writemsg(' bld dir:  %s\n' % EXSTNG_BLD, fout)
    writemsg(' hom dir:  %s\n' % HOM_DIR, fout)
    writemsg(' run dir:  %s\n' % RUN_DIR, fout)

    writemsg('\n', fout)    



def job_completed(JOB_ID, fout=None):
    """
    # ------------------------------------------------------------
    # def job_completed(JOB_ID, fout=None):
    #
    # Return True if job has finished, else return False
    #
    # Inputs:
    #     JOB_ID: job id
    #       fout: handle of open output file, if None,
    #             set to sys.stdout
    # Output:
    #    Return True/False. Raise exception if host not recognized
    # ------------------------------------------------------------
    """

    HOST = get_hostname()

    if HOST == 'DISCOVER':
        # slurm
        cmd = 'sacct --format state -n -j %s.batch' % JOB_ID
        run = sp.Popen(cmd.split(), stdout=sp.PIPE, stderr=sp.PIPE)
        output = run.communicate()
        rtrnCode = run.wait()
        if rtrnCode != 0:
            print('0:'); print(output[0]); print('1:'); print(output[1])
            raise Exception('run (sacct --format state -n -j %s.batch) failed' % JOB_ID)
        status = output[0].strip()
        if status=='CANCELLED': raise Exception('Job was CANCELLED')
        elif status=='FAILED': raise Exception('Job FAILED')
        if status=='COMPLETED': return True
        else: return False


    elif HOST=='PLEIADES':
        cmd1 = ('qstat -f -x %s' % JOB_ID).split()
        cmd2 = 'grep job_state'.split()
        run1 = sp.Popen(cmd1, stdout=sp.PIPE, stderr=sp.PIPE)
        rtrnCode = run1.wait()
        if rtrnCode != 0: raise Exception('run1 (qstat -f %s) failed' % JOB_ID)
        run2 = sp.Popen(cmd2, stdin=run1.stdout,stdout=sp.PIPE)
        rtrnCode = run2.wait()
        if rtrnCode != 0: raise Exception('run2 (grep job_state) failed')
        run1.stdout.close()
        output = run2.communicate()
        if output[1]:
            print('0:'); print(output[0]); print('1:'); print(output[1])
            raise Exception('utils:job_completed_script - something wrong')
        status = output[0].split('=')[1].strip()
        if status=='F': return True
        else: return False
    else:
        raise Exception('host [%s] not recognized' % HOST)

def git_clone(GITREPO, DIR=None, GITTAG=None, fout=None):
    """
    # --------------------------------------------------------------------------
    # Clone model from git repository.
    # NOTE: Clones model in the directory it is called from and returns
    # output of git command
    # 
    # Input:
    #        GITREPO: Directory to clone from
    #            DIR: Check out into DIR instead, if None checkout into MOD
    #         GITTAG: Check out tag GITTAG, if None checkout default tag of repo
    #           fout: handle of open output file, if None - set to sys.stdout
    # Output:
    #         output: list containing output of command (stdout and stderr)
    #  
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout

    if GITTAG:
       writemsg(' Cloning [repo: %s, tag: %s]...' % (GITREPO, GITTAG), fout)
    else:
       writemsg(' Cloning [repo: %s]...' % GITREPO, fout)

    HOST = get_hostname()

    if HOST == 'DISCOVER':
        cmd = ['/gpfsm/dulocal/sles11/other/SLES11.3/git/2.21.0/libexec/git-core/git', 'clone']
    elif HOST == 'PLEIADES':
        cmd = ['/nobackup/gmao_SIteam/git/git-2.21.0/bin/git', 'clone']

    if GITTAG: cmd.extend(['-b', ''.join(GITTAG)])

    cmd.append(GITREPO)

    if DIR: cmd.append(DIR)

    run = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)

    output = run.communicate()
    rtrnCode = run.wait()
    if rtrnCode != 0:
        print('0:'); print(output[0]); print('1:'); print(output[1])
        raise Exception('git clone failed')

    writemsg('done.\n', fout)
    return output

def git_change_g5modules(CHKDIR, G5FILE, fout=None):
    """
    # --------------------------------------------------------------------------
    # Changes the g5_modules for a git checkout
    # NOTE: Veeeeeeeery fragile
    # 
    # Input:
    #         CHKDIR: Checkout directory
    #         G5FILE: g5_modules to use in this checkout
    #           fout: handle of open output file, if None - set to sys.stdout
    #  
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout
    writemsg(' Converting checkout %s to use g5_modules from %s ...' % (CHKDIR, G5FILE), fout)

    ORIG_G5_FILE = os.path.join(CHKDIR,'@env','g5_modules')
    assert os.path.isfile(ORIG_G5_FILE)

    shutil.copy(G5FILE,ORIG_G5_FILE)
    assert filecmp.cmp(G5FILE,ORIG_G5_FILE)

    writemsg('done.\n', fout)

def git_checkout_externals(CHKDIR, EXTERN, fout=None):
    """
    # --------------------------------------------------------------------------
    # Checks out the externals from the git clone
    # 
    # Input:
    #         CHKDIR: Checkout directory
    #         EXTERN: manage_externals cfg to use
    #           fout: handle of open output file, if None - set to sys.stdout
    #  
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout
    writemsg(' Running checkout_externals on %s in %s ...' % (EXTERN, CHKDIR), fout)

    os.chdir(CHKDIR)
    assert os.path.isfile(EXTERN)

    cmd = ['checkout_externals','-e',EXTERN]
    run = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)

    print(cmd)

    output = run.communicate()
    rtrnCode = run.wait()
    if rtrnCode != 0:
        print('0:'); print(output[0]); print('1:'); print(output[1])
        raise Exception('checkout_externals failed')

    writemsg('done.\n', fout)

def git_checkout_mepo(CHKDIR, MAPLDEV, fout=None):
    """
    # --------------------------------------------------------------------------
    # Checks out the externals from the git clone
    # 
    # Input:
    #         CHKDIR: Checkout directory
    #        MAPLDEV: use mapl develop
    #           fout: handle of open output file, if None - set to sys.stdout
    #  
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout
    writemsg(' Running mepo in %s ...' % (CHKDIR), fout)

    os.chdir(CHKDIR)

    cmd1 = ['mepo', 'init']
    cmd2 = ['mepo', 'clone']
    cmd3 = ['mepo', 'develop', 'GEOSgcm_GridComp', 'GEOSgcm_App']
    if MAPLDEV:
        cmd3 += ['MAPL']

    run1 = sp.Popen(cmd1, stdout=sp.PIPE, stderr=sp.PIPE)
    rtrnCode = run1.wait()
    if rtrnCode != 0: raise Exception('run1 (mepo init) failed')

    run2 = sp.Popen(cmd2, stdin=run1.stdout,stdout=sp.PIPE)
    rtrnCode = run2.wait()
    if rtrnCode != 0: raise Exception('run2 (mepo clone) failed')

    run3 = sp.Popen(cmd3, stdin=run2.stdout,stdout=sp.PIPE)
    rtrnCode = run3.wait()
    if rtrnCode != 0: raise Exception('run3 (mepo develop) failed')

    run1.stdout.close()
    run2.stdout.close()
    output = run3.communicate()
    if output[1]:
        print('0:'); print(output[0]); print('1:'); print(output[1]); print('2:'); print(output[2])
        raise Exception('git_checkout_mepo failed')
    writemsg('done.\n', fout)

def useHemco(RUN_DIR, fout=None):
    """
    # --------------------------------------------------------------------------
    # Edit RC/GEOS_ChemGridComp.rc to use HEMCO
    #
    # Input:
    #         RUN_DIR: where RC/GEOS_ChemGridComp.rc resides
    #            fout: handle of open output file, if None - set to sys.stdout
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout
    
    writemsg(' Editing to run with HEMCO...', fout)

    # edit GEOS_ChemGridComp.rc
    # ------------
    CHEM_RC = os.path.join(RUN_DIR,'RC','GEOS_ChemGridComp.rc'); assert os.path.isfile(CHEM_RC)
    fin = open(CHEM_RC, 'r'); lines = fin.readlines(); fin.close()
    sout = open(CHEM_RC, 'w')
    for line in lines:
        if ('ENABLE_HEMCO:' in line):
            line = line.replace('FALSE', 'TRUE')
        sout.write(line)
    sout.close()

    writemsg('done.\n', fout)

def useOpsGOCART(RUN_DIR, fout=None):
    """
    # --------------------------------------------------------------------------
    # Edit cap_restart to use run in 2015
    #
    # Input:
    #         RUN_DIR: where cap_restart resides
    #            fout: handle of open output file, if None - set to sys.stdout
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout

    writemsg(' Editing to run with Ops GOCART by changing year to 2015...', fout)

    # edit cap_restart
    # ----------------
    CAP_RESTART_FILE = os.path.join(RUN_DIR,'cap_restart'); assert os.path.isfile(CAP_RESTART_FILE)
    fin = open(CAP_RESTART_FILE, 'r'); lines = fin.readlines(); fin.close()
    sout = open(CAP_RESTART_FILE, 'w')
    for line in lines:
        if ('2000' in line):
            line = line.replace('2000', '2015')
        sout.write(line)
    sout.close()

    writemsg('done.\n', fout)

def are_dir_trees_equal(dir1, dir2):
    """
    Compare two directories recursively. Files in each directory are
    assumed to be equal if their names and contents are equal.

    @param dir1: First directory path
    @param dir2: Second directory path

    @return: True if the directory trees are the same and 
        there were no errors while accessing the directories or files, 
        False otherwise.
   """

    dirs_cmp = filecmp.dircmp(dir1, dir2)
    if len(dirs_cmp.left_only)>0 or len(dirs_cmp.right_only)>0 or \
        len(dirs_cmp.funny_files)>0:
        return False
    (_, mismatch, errors) =  filecmp.cmpfiles(
        dir1, dir2, dirs_cmp.common_files, shallow=False)
    if len(mismatch)>0 or len(errors)>0:
        return False
    for common_dir in dirs_cmp.common_dirs:
        new_dir1 = os.path.join(dir1, common_dir)
        new_dir2 = os.path.join(dir2, common_dir)
        if not are_dir_trees_equal(new_dir1, new_dir2):
            return False
    return True


def useSingleNode(RUN_DIR, fout=None):
    """
    # --------------------------------------------------------------------------
    # Edit cap_restart to use run in 2015
    #
    # Input:
    #         RUN_DIR: where cap_restart resides
    #            fout: handle of open output file, if None - set to sys.stdout
    # --------------------------------------------------------------------------
    """

    if not fout: fout = sys.stdout

    writemsg(' Editing to run with Ops GOCART by changing year to 2015...', fout)

    # edit cap_restart
    # ----------------
    AGCM_RC_FILE = os.path.join(RUN_DIR,'AGCM.rc'); assert os.path.isfile(AGCM_RC_FILE)
    fin = open(AGCM_RC_FILE, 'r'); lines = fin.readlines(); fin.close()
    sout = open(AGCM_RC_FILE, 'w')
    for line in lines:
        if ('NX:' in line):
            line = line.replace('4', '2')
        if ('NY:' in line):
            line = line.replace('24', '6')
            line = line.replace('12', '6')
        sout.write(line)
    sout.close()

    writemsg('done.\n', fout)

def is_tool(name):
    """Check whether `name` is on PATH."""

    from distutils.spawn import find_executable

    return find_executable(name) is not None

def nc4_compare(bas_file, cur_file, debug=None, toolToUse='nccmp', AllowNan=None):
    """
    # --------------------------------------------------------------------------
    # Compare two netcdf files
    #
    # Input:
    #         bas_file: baseline file
    #         cur_file: current file
    #            debug: debug prints
    # Output:
    #         0 for success, 1 for failure
    # --------------------------------------------------------------------------
    """

    if 'cdo' in toolToUse and is_tool('cdo'):
        rc = cdo_compare(bas_file, cur_file, diff='cdo', debug=debug)
    elif 'nccmp' in toolToUse and is_tool('nccmp'):
        rc = nccmp_compare(bas_file, cur_file, diff='nccmp', debug=debug, AllowNan=AllowNan)
    else:
        print("Neither nccmp or cdo found in path!!!")
        raise Exception('no nc4 comparator found')

    return rc

def nccmp_compare(bas_file, cur_file, diff='nccmp', debug=None, AllowNan=None):
    """
    # --------------------------------------------------------------------------
    # Compare two netcdf files using nccmp
    #
    # Input:
    #         bas_file: baseline file
    #         cur_file: current file
    #             diff: differencer
    #            debug: debug prints
    # Output:
    #         0 for success, 1 for failure
    # --------------------------------------------------------------------------
    """

    if AllowNan:
        cmp_options = '-BdN'
    else:
        cmp_options = '-Bd'

    cmd = [diff, cmp_options, bas_file, cur_file]
    if debug: 
        print("\nUsing", diff)
        print("Running ", cmd)
    run = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)
    rc = run.wait()
    return rc

def cdo_compare(bas_file, cur_file, diff='cdo', debug=None):
    """
    # --------------------------------------------------------------------------
    # Compare two netcdf files using cdo
    #
    # Input:
    #         bas_file: baseline file
    #         cur_file: current file
    #             diff: differencer
    #            debug: debug prints
    # Output:
    #         0 for success, 1 for failure
    # --------------------------------------------------------------------------
    """

    cmd = [diff, '--no_warnings','-Q', '-s', 'diffn', bas_file, cur_file]
    if debug: 
        print("\nUsing", diff)
        print("Running ", cmd)
    run = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)
    output = run.communicate()
    if len(output[1]) > 0:
        rc = 1
    else:
        if len(output[0].strip().split())==0:
            rc = 0
        elif int(output[0].strip().split()[0])==0:
            rc = 0
        else:
            rc = 1
    return rc

def cmp_compare(bas_file, cur_file, diff='cmp', debug=None):
    """
    # --------------------------------------------------------------------------
    # Compare two binary files using cmp
    #
    # Input:
    #         bas_file: baseline file
    #         cur_file: current file
    #             diff: differencer
    #            debug: debug prints
    # Output:
    #         0 for success, 1 for failure
    # --------------------------------------------------------------------------
    """

    cmd = [diff, bas_file, cur_file]
    if debug: 
        print("\nUsing", diff)
        print("Running ", cmd)
    run = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)
    rc = run.wait()
    return rc
