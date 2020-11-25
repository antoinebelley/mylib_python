#!/usr/bin/env python3
import os, sys, time, subprocess, re, itertools
import numpy as np
if(__package__==None or __package__==""):
    import PeriodicTable
    import Operator
    import TransitionDensity
else:
    from . import PeriodicTable
    from . import Operator
    from . import TransitionDensity

def _none_check(var, var_name):
    if(var==None):
        print("{:s} can't be None.".format(var_name))
        return True

def _ZNA_from_str(Nucl):
    isdigit = re.search(r'\d+', Nucl)
    A = int( isdigit.group() )
    asc = Nucl[:isdigit.start()] + Nucl[isdigit.end():]
    asc = asc.lower()
    asc = asc[0].upper() + asc[1:]
    Z = PeriodicTable.periodic_table.index(asc)
    N = A-Z
    return Z, N, A

def _str_to_state(string):
    """
    0+1 -> ('0', '+', 1)
    1+1 -> ('1', '+', 1)
    0.5+1 -> ('1/2', '+', 1)
    0.5-1 -> ('1/2', '-', 1)
    ...
    """
    if( string.find("+") != -1 ):
        J2 = int( 2*float( string.split("+")[0] ))
        nth = int( string.split("+")[1] )
        prty = "+"
    if( string.find("-") != -1 ):
        J2 = int( 2*float( string.split("-")[0] ))
        nth = int( string.split("-")[1] )
        prty = "-"
    if( J2%2==0 ): return (str(J2//2), prty, nth)
    if( J2%2==1 ): return (str(J2)+"/2", prty, nth)


class kshell_scripts:
    def __init__(self, kshl_dir=None, fn_snt=None, Nucl=None, states=None, hw_truncation=None, run_args={"beta_cm":0, "mode_lv_hdd":0}, verbose=False):
        self.kshl_dir = kshl_dir
        self.Nucl = Nucl
        self.verbose=verbose
        if(Nucl != None): self.Z, self.N, self.A = _ZNA_from_str(self.Nucl)
        self.states = states
        self.hw_truncation=hw_truncation
        self.plot_position=0
        self.run_args=run_args
        self.edict_previous={}
        self.fn_snt = fn_snt
        if(fn_snt != None and states != None):
            self.fn_ptns = {}
            self.fn_wfs = {}
            for state in self.states.split(","):
                state_str = self._state_string(state)
                self.fn_ptns[state] = "{:s}_{:s}_{:s}.ptn".format(self.Nucl, os.path.splitext(os.path.basename(self.fn_snt))[0], state_str[-1] )
                self.fn_wfs[state] = "{:s}_{:s}_{:s}.wav".format(self.Nucl, os.path.splitext(os.path.basename(self.fn_snt))[0], state_str )
    def get_x_position(self): return self.plot_position
    def set_snt_file(self, fn_snt, set_other_files=False):
        self.fn_snt = fn_snt
        if(set_other_files):
            self.fn_ptns = {}
            self.fn_wfs = {}
            for state in self.states.split(","):
                state_str = self._state_string(state)
                self.fn_ptns[state] = "{:s}_{:s}_{:s}.ptn".format(self.Nucl, os.path.splitext(os.path.basename(self.fn_snt))[0], state_str[-1] )
                self.fn_wfs[state] = "{:s}_{:s}_{:s}.wav".format(self.Nucl, os.path.splitext(os.path.basename(self.fn_snt))[0], state_str )
    def set_nucl(self, nucl):
        self.Nucl = nucl
        self.Z, self.N, self.A = _ZNA_from_str(self.Nucl)
    def set_run_args(self, run_args):
        self.run_args = run_args
    def get_wf_index( self, fn_summary ):
        jpn_to_idx = {}
        f = open( fn_summary, "r" )
        lines = f.readlines()
        f.close()
        logs = set()
        idxs = {}
        for line in lines[5:]:
            dat = line.split()
            if( len(dat) == 0 ): continue
            if( dat[-1] in logs ):
                idxs[ dat[-1] ] += 1
            else:
                idxs[ dat[-1] ] = 1
                logs.add( dat[-1] )
            jpn_to_idx[(dat[1],dat[2],int(dat[3]))] = (dat[-1], idxs[ dat[-1] ])
        return jpn_to_idx
    def _state_string(self, state):
        """
        example:
        0+1 -> j0p
        0+2 -> j0p
        2+2 -> j4p
        0.5-2 -> j1n
        1.5-2 -> j3n
        +1 -> m0p or m1p
        -1 -> m0n or m1n
        """
        isdigit = re.findall(r'\d+', state)
        if( len(isdigit)==3 ):
            if( state.find("+")!=-1): state_str = "j{:d}p".format(int(2*int(isdigit[0])+1))
            if( state.find("-")!=-1): state_str = "j{:d}n".format(int(2*int(isdigit[0])+1))
        elif( len(isdigit)==2 ):
            if( state.find("+")!=-1): state_str = "j{:d}p".format(int(2*int(isdigit[0])))
            if( state.find("-")!=-1): state_str = "j{:d}n".format(int(2*int(isdigit[0])))
        elif( len(isdigit)==1 ):
            if( state.find("+")!=-1): state_str = "m0p"
            if( state.find("-")!=-1): state_str = "m0n"
            if(self.A%2==1):
                if( state.find("+")!=-1): state_str = "m1p"
                if( state.find("-")!=-1): state_str = "m1n"
        return state_str

    def _i2prty(self, i):
        if(i == 1): return '+'
        else: return '-'
    def get_occupation(self, logs=None):
        if(logs==None):
            logs = []
            states = self.states.split(",")
            for state in states:
                state_str = self._state_string(state)
                log = "log_{:s}_{:s}_{:s}.txt".format(self.Nucl, os.path.splitext( os.path.basename(self.fn_snt))[0], state_str)
                logs.append(log)
        e_data = {}
        for log in logs:
            f = open(log,"r")
            while True:
                line = f.readline()
                if(not line): break
                if(line[6:10] == "<H>:"):
                    dat = line.split()
                    n_eig= int(dat[0])
                    ene  = float(dat[2])
                    mtot = int(dat[6][:-2])
                    prty = int(dat[8])
                    prty = self._i2prty(self,prty)
                    while ene in e_data: ene += 0.000001
                    line = f.readline()
                    if line[42:45] != ' T:': continue
                    tt = int(line[45:48])
                    line = f.readline()
                    data = line.split()
                    if(line[0:7] ==" <p Nj>"):
                        plist = []
                        for i in range(len(data)-2):
                            plist.append(float(data[i+2]))
                    line = f.readline()
                    data = line.split()
                    if(line[0:7] ==" <n Nj>"):
                        nlist = []
                        for i in range(len(data)-2):
                            nlist.append(float(data[i+2]))
                    while len(line)!=0:
                        line = f.readline()
                        data = line.split()
                        if(line[0:4] ==" hw:"):
                            hws = {}
                            for i in range(len(data)-1):
                                hw, prob = data[i+1].split(":")
                                hws[int(hw)] = float(prob)
                            break
                    e_data[ round(ene,3) ] = (log, mtot, prty, n_eig, tt, plist, nlist, hws)
            f.close()
        return e_data

    def run_kshell(self, header="", batch_cmd=None, run_cmd=None, dim_cnt=False, gen_partition=False, fn_script=None):
        if(fn_script==None):
            fn_script = "{:s}_{:s}".format(self.Nucl, os.path.splitext(os.path.basename(self.fn_snt))[0])
            if(self.run_args != None):
                if( 'beta_cm' in self.run_args and self.run_args['beta_cm'] != 0): fn_script += "_betacm{:d}".format(self.run_args['beta_cm'])
            if(self.hw_truncation != None): fn_script += "_hw" + str(self.hw_truncation)
        if(not os.path.isfile(self.fn_snt)):
            print(self.fn_snt, "not found")
            return
        unnatural=False
        if( self.states.find("-") != -1 and self.states.find("+")!=-1 ): unnatural=True
        f = open('ui.in','w')
        f.write('\n')
        f.write(self.fn_snt+'\n')
        f.write(self.Nucl+'\n')
        f.write(fn_script+'\n')
        f.write(self.states+'\n')
        if(self.hw_truncation==None): f.write('\n')
        else:
            f.write('2\n')
            f.write(str(self.hw_truncation)+'\n')
        if(unnatural):
            if(self.hw_truncation==None): f.write('\n')
            else:
                f.write('2\n')
                f.write(str(self.hw_truncation)+'\n')
        if(self.run_args!=None):
            for key in self.run_args.keys():
                f.write('{:s}={:s}\n'.format(key, str(self.run_args[key])))
        f.write('\n')
        f.write('\n')
        f.write('\n')
        f.close()
        if(self.verbose): cmd = 'python2 '+self.kshl_dir+'/kshell_ui.py < ui.in'
        if(not self.verbose): cmd = 'python2 '+self.kshl_dir+'/kshell_ui.py < ui.in silent'
        subprocess.call(cmd, shell=True)
        f = open(fn_script+".sh", "r")
        lines = f.readlines()
        f.close()
        prt = ""
        for line in lines[:3]:
            prt += line
        if( header != "" ): prt = header
        for line in lines[3:]:
            if(line.find("./kshell.exe") != -1):
                if( run_cmd == None ): prt += "./kshell.exe " + line[18:]
                if( run_cmd != None ): prt += run_cmd + " ./kshell.exe " + line[18:]
            else:
                prt += line
        f = open(fn_script+".sh", "w")
        f.write(prt)
        f.close()

        subprocess.call("rm ui.in", shell=True)
        if(gen_partition): return
        if( dim_cnt ):
            if( os.path.exists( fn_script+'_p.ptn' ) ):
                cmd = 'python2 ' + self.kshl_dir+'/count_dim.py ' + fn_snt + ' ' + fn_script + '_p.ptn'
                subprocess.call(cmd, shell=True)
            if( os.path.exists( fn_script+'_n.ptn' ) ):
                cmd = 'python2 ' + self.kshl_dir+'/count_dim.py ' + fn_snt + ' ' + fn_script + '_n.ptn'
                subprocess.call(cmd, shell=True)
        else:
            fn_script += ".sh"
            os.chmod(fn_script, 0o755)
            if(batch_cmd == None): cmd = "./" + fn_script
            if(batch_cmd != None): cmd = batch_cmd + " " + fn_script
            subprocess.call(cmd, shell=True)

        if(batch_cmd != None): time.sleep(1)

    def run_kshell_lsf(self, fn_ptn_init, fn_ptn, fn_wf, fn_wf_out, J2, \
            op=None, fn_input=None, n_vec=100, header="", batch_cmd=None, run_cmd=None, \
            fn_operator=None, operator_irank=0, operator_nbody=1, operator_iprty=1):
        fn_script = os.path.basename(os.path.splitext(fn_wf_out)[0]) + ".sh"
        fn_out = "log_" + os.path.basename(os.path.splitext(fn_wf_out)[0]) + ".txt"
        if(fn_input==None): fn_input = os.path.basename(os.path.splitext(fn_wf_out)[0]) + ".input"
        if(op==None and fn_operator==None):
            print("Put either op or fn_operator")
            return
        if(op!=None and fn_operator!=None):
            print("You cannot put both op and fn_operator")
            return
        if(not os.path.isfile(self.fn_snt)):
            print(self.fn_snt, "not found")
            return
        cmd = "cp " + self.kshl_dir + "/kshell.exe ./"
        subprocess.call(cmd,shell=True)
        prt = header + '\n'
        #prt += 'echo "start runnning ' + fn_out + ' ..."\n'
        prt += 'cat >' + fn_input + ' <<EOF\n'
        prt += '&input\n'
        prt += '  fn_int   = "' + self.fn_snt + '"\n'
        prt += '  fn_ptn = "' + fn_ptn + '"\n'
        prt += '  fn_ptn_init = "' + fn_ptn_init + '"\n'
        prt += '  fn_load_wave = "' + fn_wf + '"\n'
        prt += '  fn_save_wave = "' + fn_wf_out + '"\n'
        prt += '  max_lanc_vec = '+str(n_vec)+'\n'
        prt += '  n_eigen = '+str(n_vec)+'\n'
        prt += '  n_restart_vec = '+str(min(n_vec,200))+'\n'
        prt += '  mtot = '+str(J2)+'\n'
        prt += '  maxiter = 1\n'
        prt += '  is_double_j = .true.\n'
        if(op!=None): prt += '  op_type_init = "'+str(op)+'"\n'
        if(fn_operator!=None):
            prt += '  fn_operator = "'+str(fn_operator)+'"\n'
            prt += '  operator_irank = '+str(operator_irank)+'\n'
            prt += '  operator_nbody = '+str(operator_nbody)+'\n'
            prt += '  operator_iprty = '+str(operator_iprty)+'\n'
        prt += '  eff_charge = 1.0, 0.0\n'
        prt += '  e1_charge = 1.0, 0.0\n'
        if(self.run_args!=None):
            for key in self.run_args.keys():
                prt += '{:s}={:s}\n'.format(key, str(self.run_args[key]))
        prt += '&end\n'
        prt += 'EOF\n'
        if(run_cmd == None): prt += './kshell.exe ' + fn_input + ' > ' + fn_out + ' 2>&1\n'
        if(run_cmd != None): prt += run_cmd + ' ./kshell.exe ' + fn_input + ' > ' + fn_out + ' 2>&1\n\n\n'
        prt += 'rm -f tmp_snapshot_' + fn_ptn + "_" + str(J2) + "_* " + \
                'tmp_lv_' + fn_ptn + '_' + str(J2) + "_* " + \
                fn_input + '\n\n\n'
        prt += './collect_logs.py log_*' + self.basename() + '* > ' + \
                self.summary_filename() + '\n\n'
        f = open(fn_script,'w')
        f.write(prt)
        f.close()
        os.chmod(fn_script, 0o755)
        if(batch_cmd == None): cmd = "./" + fn_script
        if(batch_cmd != None): cmd = batch_cmd + " " + fn_script
        subprocess.call(cmd, shell=True)
        if(batch_cmd != None): time.sleep(1)

    def basename(self):
        return "{:s}_{:s}".format(self.Nucl, os.path.splitext(os.path.basename(self.fn_snt))[0])

    def summary_filename(self):
        fn_summary = "summary_{:s}_{:s}".format(self.Nucl, os.path.splitext(os.path.basename(self.fn_snt))[0])
        if(self.run_args != None):
            if( 'beta_cm' in self.run_args and self.run_args['beta_cm'] != 0): fn_summary += "_betacm{:d}".format(self.run_args['beta_cm'])
        if(self.hw_truncation != None): fn_summary += "_hw" + str(self.hw_truncation)
        fn_summary += ".txt"
        return fn_summary

    def summary_to_dictionary(self, comment_snt="!"):
        fn_summary = self.summary_filename()
        H = Operator()
        H.read_operator_file(self.fn_snt,comment=comment_snt)
        if(not os.path.exists(fn_summary)): return {}
        f = open(fn_summary,'r')
        lines = f.readlines()
        f.close()
        edict={}
        for line in lines:
            data = line.split()
            try:
                N = int(data[0])
                J = data[1]
                P = data[2]
                i = int(data[3])
                e = float(data[5])
                eex = float(data[6])
                edict[(J,P,i)] = e + H.get_0bme()
            except:
                continue
        return edict
    def plot_levels(self, ax, edict=None, \
            absolute=False, show_Jpi=False, connect=True, bar_width=0.3, lw=1, window_size=4, color_mode="parity"):
        if(edict==None): edict = self.summary_to_dictionary()
        self._plot_levels(ax, edict, \
                absolute=absolute, show_Jpi=show_Jpi, connect=connect, \
                bar_width=bar_width, lw=lw, window_size=window_size, color_mode=color_mode)
    def set_Jpi_labels(self, ax, edict=None, absolute=False, lw=1, bar_width=0.3, window_size=4, color_mode="parity"):
        if(edict==None): edict = self.summary_to_dictionary()
        if(edict=={}): return
        if(not absolute):
            tmp = edict
            Emin = np.inf
            for E in tmp.values():
                Emin = min(Emin, E)
            for key in tmp.keys():
                edict[key] = tmp[key]-Emin
        x = self.plot_position-1
        fs = 2 # fontsize is assumed to be 2 mm
        bbox = ax.get_window_extent()
        width, height = bbox.width, bbox.height # in pixel
        width *= 2.54/100 # in cm
        height *= 2.54/100 # in cm
        h = 10 * height / window_size # mm / MeV
        levels = sorted(edict.items(), key=lambda x:x[1])
        first = levels[0]
        key = first[0]
        y = first[1]
        label = "$"+key[0]+"^{"+key[1]+"}_{"+str(key[2])+"}$"
        ax.plot([x+bar_width,x+bar_width+0.2],[y,y],lw=0.8*lw,c=self._get_color(key,color_mode),ls=":")
        ax.annotate(label, xy=(x+bar_width+0.2,y), color=self._get_color(key,color_mode))
        if(absolute): y_back = y
        else: y_back = 0
        for i in range(1,len(levels)):
            level = levels[i]
            key = level[0]
            e = level[1]
            label = "$"+key[0]+"^{"+key[1]+"}_{"+str(key[2])+"}$"
            if((e-y)*h < fs): y+= (fs+0.2)/h
            else: y=e
            #print(key,f'{e:12.6f} {y_back:12.6f} {y:12.6f}')
            ax.plot([x+bar_width,x+bar_width+0.2],[e,y],lw=0.8*lw,c=self._get_color(key,color_mode),ls=":")
            ax.annotate(label, xy=(x+bar_width+0.2,y),color=self._get_color(key,color_mode))
            y_back=y

    def _plot_levels(self, ax, edict, \
            absolute=False, show_Jpi=False, connect=True, bar_width=0.3, lw=1, window_size=4, color_mode="parity"):
        if(not absolute):
            tmp = edict
            Emin = np.inf
            for E in tmp.values():
                Emin = min(Emin, E)
            for key in tmp.keys():
                edict[key] = tmp[key]-Emin
        x = self.plot_position
        for key in edict.keys():
            y = edict[key]
            ax.plot([x-bar_width,x+bar_width],[y,y],lw=lw,c=self._get_color(key,color_mode))
        if(connect and len(self.edict_previous)!=0):
            for key in self.edict_previous.keys():
                if(key in edict):
                    yl = self.edict_previous[key]
                    yr = edict[key]
                    ax.plot([x-1+bar_width,x-bar_width],[yl,yr],lw=0.8*lw,ls=":",c=self._get_color(key,color_mode))
        self.plot_position+=1
        if(show_Jpi): self.set_Jpi_labels(ax, edict, absolute=absolute, lw=lw, bar_width=bar_width, window_size=window_size, color_mode=color_mode)
        self.edict_previous=edict
    def _get_color(self, key, color_mode):
        color_list_p = ['red','salmon','orange','darkgoldenrod','gold','olive', 'lime','forestgreen','turquoise','teal','skyblue']
        color_list_n = ['navy','blue','mediumpurple','blueviolet','mediumorchid','purple','magenta','pink','crimson']
        if(self.A%2==0): Jdouble = int(key[0])*2
        if(self.A%2==1): Jdouble = int(key[0][:-2])
        P = key[1]
        if(color_mode=="parity"):
            if(P=="+"): return "red"
            if(P=="-"): return "blue"
        elif(color_mode=="spin_parity"):
            idx = int(Jdouble/2)
            if(P=="+"): return color_list_p[idx%len(color_list_p)]
            if(P=="-"): return color_list_n[idx%len(color_list_n)]



class transit_scripts:
    def __init__(self, kshl_dir=None):
        self.kshl_dir = kshl_dir
        self.filenames = {}

    def set_filenames(self, ksh_l, ksh_r, states_list=None, calc_SF=False):
        if(states_list==None):
            states_list = [(x,y) for x,y in itertools.product( ksh_l.states.split(","), ksh_r.states.split(",") )]
        bra_side = ksh_l
        ket_side = ksh_r
        flip=False

        if( ksh_l.Z < ksh_r.Z ):
            bra_side = ksh_r
            ket_side = ksh_l
            flip=True
        if( ksh_l.A < ksh_r.A ):
            bra_side = ksh_r
            ket_side = ksh_l
            flip=True

        for states in states_list:
            state_l = states[0]
            state_r = states[1]
            if(flip):
                state_l = states[1]
                state_r = states[0]
            str_l = bra_side._state_string(state_l)
            str_r = ket_side._state_string(state_r)
            fn_density = "density_{:s}_{:s}{:s}_{:s}{:s}.txt".format(os.path.splitext( os.path.basename( ket_side.fn_snt ) )[0], bra_side.Nucl,str_l, ket_side.Nucl,str_r )
            if(calc_SF): fn_density = "SF_{:s}_{:s}{:s}_{:s}{:s}.txt".format(os.path.splitext( os.path.basename( ket_side.fn_snt ) )[0], bra_side.Nucl,str_l, ket_side.Nucl,str_r )
            self.filenames[(state_l,state_r)] = fn_density
        return flip

    def calc_density(self, ksh_l, ksh_r, states_list=None, header="", batch_cmd=None, run_cmd=None, i_wfs=None, calc_SF=False):
        if(states_list==None):
            states_list = [(x,y) for x,y in itertools.product( ksh_l.states.split(","), ksh_r.states.split(",") )]
        bra_side = ksh_l
        ket_side = ksh_r
        flip=False

        if( ksh_l.Z < ksh_r.Z ):
            bra_side = ksh_r
            ket_side = ksh_l
            flip=True
        if( ksh_l.A < ksh_r.A ):
            bra_side = ksh_r
            ket_side = ksh_l
            flip=True

        density_files = []
        for states in states_list:
            state_l = states[0]
            state_r = states[1]
            if(flip):
                state_l = states[1]
                state_r = states[0]
            str_l = bra_side._state_string(state_l)
            str_r = ket_side._state_string(state_r)
            fn_density = "density_{:s}_{:s}{:s}_{:s}{:s}.txt".format(os.path.splitext( os.path.basename( ket_side.fn_snt ) )[0], bra_side.Nucl,str_l, ket_side.Nucl,str_r )
            if(calc_SF): fn_density = "SF_{:s}_{:s}{:s}_{:s}{:s}.txt".format(os.path.splitext( os.path.basename( ket_side.fn_snt ) )[0], bra_side.Nucl,str_l, ket_side.Nucl,str_r )

            density_files.append(fn_density)
            fn_script = os.path.splitext(fn_density)[0] + ".sh"
            fn_input = os.path.splitext(fn_density)[0] + ".input"
            cmd = "cp " + self.kshl_dir + "/transit.exe ./"
            subprocess.call(cmd,shell=True)
            prt = header + '\n'
            #prt += 'echo "start runnning ' + fn_density + ' ..."\n'
            prt += 'cat >' + fn_input + ' <<EOF\n'
            prt += '&input\n'
            prt += '  fn_int   = "' + ket_side.fn_snt + '"\n'
            prt += '  fn_ptn_l = "' + bra_side.fn_ptns[state_l]+ '"\n'
            prt += '  fn_ptn_r = "' + ket_side.fn_ptns[state_r]+ '"\n'
            prt += '  fn_load_wave_l = "' + bra_side.fn_wfs[state_l] + '"\n'
            prt += '  fn_load_wave_r = "' + ket_side.fn_wfs[state_r] + '"\n'
            if(i_wfs!=None):
                prt += '  n_eig_lr_pair = '
                for lr in i_wfs:
                    if(flip):
                        prt += str(lr[1]) + ', ' + str(lr[0]) + ', '
                    else:
                        prt += str(lr[0]) + ', ' + str(lr[1]) + ', '
                prt += '\n'
            prt += '  hw_type = 2\n'
            prt += '  eff_charge = 1.5, 0.5\n'
            prt += '  gl = 1.0, 0.0\n'
            prt += '  gs = 3.91, -2.678\n'
            if(not calc_SF): prt += '  is_tbtd = .true.\n'
            prt += '&end\n'
            prt += 'EOF\n'
            if(run_cmd == None):
                prt += './transit.exe ' + fn_input + ' > ' + fn_density + ' 2>&1\n'
            if(run_cmd != None):
                prt += run_cmd + ' ./transit.exe ' + fn_input + ' > ' + fn_density + ' 2>&1\n'
            prt += 'rm ' + fn_input + '\n'
            f = open(fn_script,'w')
            f.write(prt)
            f.close()
            os.chmod(fn_script, 0o755)
            if(batch_cmd == None): cmd = "./" + fn_script
            if(batch_cmd != None): cmd = batch_cmd + " " + fn_script
            subprocess.call(cmd, shell=True)
            if(batch_cmd != None): time.sleep(1)
        return density_files, flip

    def calc_espe(self, kshl, snts=None, states_dest="+20,-20", header="", batch_cmd=None, run_cmd=None, step="full", mode="hole", N_states=None):
        """
        snts = [ snt_file_for_Z-1_N, snt_file_for_Z_N-1, snt_file_for_Z+1_N, snt_file_for_Z_N+1 ]
        """
        if(mode=="hole"):
            min_idx = 0
            max_idx = 2
        elif(mode=="particle"):
            min_idx = 2
            max_idx = 4
        else:
            min_idx = 0
            max_idx = 4
        if(snts==None):
            snts = [kshl.fn_snt] * 4
        if(step=="diagonalize" or step=="full"):
            kshl.run_kshell(header=header, batch_cmd=batch_cmd, run_cmd=run_cmd)
            for idx in range(min_idx,max_idx):
                fn_snt = snts[idx]
                if(idx==0): Z, N = kshl.Z-1, kshl.N
                if(idx==1): Z, N = kshl.Z, kshl.N-1
                if(idx==2): Z, N = kshl.Z+1, kshl.N
                if(idx==3): Z, N = kshl.Z, kshl.N+1
                Nucl = "{:s}{:d}".format(PeriodicTable.periodic_table[Z],Z+N)
                kshl_tr = kshell_scripts(kshl_dir=kshl.kshl_dir, fn_snt=fn_snt, Nucl=Nucl, states=states_dest)
                kshl_tr.run_kshell(header=header, batch_cmd=batch_cmd, run_cmd=run_cmd)
        if(step=="density" or step=="full"):
            for idx in range(min_idx,max_idx):
                fn_snt = snts[idx]
                if(idx==0): Z, N = kshl.Z-1, kshl.N
                if(idx==1): Z, N = kshl.Z, kshl.N-1
                if(idx==2): Z, N = kshl.Z+1, kshl.N
                if(idx==3): Z, N = kshl.Z, kshl.N+1
                Nucl = "{:s}{:d}".format(PeriodicTable.periodic_table[Z],Z+N)
                kshl_tr = kshell_scripts(kshl_dir=kshl.kshl_dir, fn_snt=fn_snt, Nucl=Nucl, states=states_dest)
                trs = transit_scripts(kshl_dir=kshl.kshl_dir)
                trs.calc_density(kshl,kshl_tr,calc_SF=True)
        # final step
        espe = {}
        sum_sf = {}
        for idx in range(min_idx,max_idx):
            fn_snt = snts[idx]
            if(idx==0): Z, N = kshl.Z-1, kshl.N
            if(idx==1): Z, N = kshl.Z, kshl.N-1
            if(idx==2): Z, N = kshl.Z+1, kshl.N
            if(idx==3): Z, N = kshl.Z, kshl.N+1
            Nucl = "{:s}{:d}".format(PeriodicTable.periodic_table[Z],Z+N)
            kshl_tr = kshell_scripts(kshl_dir=kshl.kshl_dir, fn_snt=fn_snt, Nucl=Nucl, states=states_dest)
            trs = transit_scripts(kshl_dir=kshl.kshl_dir)
            flip = trs.set_filenames(kshl, kshl_tr, calc_SF=True)
            if(flip):
                Hm_bra = Operator(filename = kshl_tr.fn_snt)
                Hm_ket = Operator(filename = kshl.fn_snt)
            else:
                Hm_bra = Operator(filename = kshl.fn_snt)
                Hm_ket = Operator(filename = kshl_tr.fn_snt)
            for key in trs.filenames.keys():
                fn = trs.filenames[key]
                espe_each, sum_sf_each = trs.read_sf_file(fn, Hm_bra, Hm_ket, N_states=N_states)
                for key in espe_each:
                    if( key in espe ):
                        espe[key] += espe_each[key]
                        sum_sf[key] += sum_sf_each[key]
                    else:
                        espe[key] = espe_each[key]
                        sum_sf[key] = sum_sf_each[key]
        return espe, sum_sf
    def read_sf_file(self,fn, Hm_bra, Hm_ket, N_states=None):
        f = open(fn,'r')
        lines = f.readlines()
        f.close()
        espe = {}
        sum_sfs = {}
        read=False
        energy = 0.0
        sum_sf=0.0
        for line in lines:
            if( line[:7] == "orbit :" ):
                data = line.split()
                n, l, j, pn = int(data[2]), int(data[3]), int(data[4]), int(data[5])
                label = (n,l,j,pn)
            if( line[:51]==" 2xJf      Ef      2xJi     Ei       Ex       C^2*S" ):
                read=True
            else:
                if(read):
                    data = line.split()
                    if(len(data)==0):
                        read=False
                        espe[label] = energy
                        sum_sfs[label] = sum_sf
                        print("{:s}{:4d}{:4d}{:4d}{:4d}{:12.6f}".format(fn,*label,sum_sf))
                        energy = 0.0
                        sum_sf = 0.0
                        continue
                    i_bra = int(data[1][:-1])
                    i_ket = int(data[4][:-1])
                    en_bra = float(data[2]) + Hm_bra.get_0bme()
                    en_ket = float(data[5]) + Hm_ket.get_0bme()
                    if(N_states != None):
                        if(i_bra > N_states): continue
                        if(i_ket > N_states): continue
                    CS = float(data[7]) / (label[2]+1)
                    sum_sf += CS * (label[2]+1)
                    energy += CS * (en_bra - en_ket)
                else:
                    continue
        return espe, sum_sfs

class kshell_toolkit:
    def calc_exp_vals(kshl_dir, fn_snt, fn_op, Nucl, states_list, hw_truncation=None,
            run_args={"beta_cm":0, "mode_lv_hdd":0}, Nucl_daughter=None, fn_snt_daughter=None,
            op_rankJ=0, op_rankP=1, op_rankZ=0, op_nbody=0, verbose=False, step="kshell"):
        """
        This would have redundant steps, but easy to run. Do not use for a big run.
        inputs:
            kshel_dir: path to kshell exe files
            fn_snt: file name of snt
            Nucl: target nuclide
            states_list: combinations of < bra | and | ket >
                ex.) even-mass case states_list should be like [(0+1, 0+1), (0+1, 2+2)]: < first 0+ | Op | first 0+ > and <first 0+ | Op | second 2+ >
                     odd-mass case state_list should be like [(0.5+1, 0.5+1), ]: < first 1/2+ | Op | first 1/2+ >
        """
        if(Nucl_daughter==None): Nucl_daughter=Nucl
        if(fn_snt_daughter==None): fn_snt_daughter=fn_snt
        op = Operator(filename=fn_op, rankJ=op_rankJ, rankP=op_rankP, rankZ=op_rankZ)
        if(step=="kshell"):
            exp_vals = []
            for lr in states_list:
                bra = lr[0]
                ket = lr[1]
                if( bra.find("+") != -1 ): Jbra = float( bra.split("+")[0] )
                if( bra.find("-") != -1 ): Jbra = float( bra.split("-")[0] )
                if( ket.find("+") != -1 ): Jket = float( ket.split("+")[0] )
                if( ket.find("-") != -1 ): Jket = float( ket.split("-")[0] )
                if( bra.find("+") != -1 ): i_bra = int( bra.split("+")[1] )
                if( bra.find("-") != -1 ): i_bra = int( bra.split("-")[1] )
                if( ket.find("+") != -1 ): i_ket = int( ket.split("+")[1] )
                if( ket.find("-") != -1 ): i_ket = int( ket.split("-")[1] )
                if(bra == ket and Nucl==Nucl_daughter and fn_snt==fn_snt_daughter):
                    kshl = kshell_scripts(kshl_dir=kshl_dir, fn_snt=fn_snt, Nucl=Nucl, states=bra, hw_truncation=hw_truncation, run_args=run_args, verbose=True)
                    kshl.run_kshell()
                    if(verbose): print("calculating density: <" + str(i) + "| Density |" + str(i) + ">")
                    trs = transit_scripts(kshl_dir=kshl_dir)
                    fn_den, flip = trs.calc_density(kshl, kshl, states_list=[lr,], i_wfs=[(i_ket, i_ket),])
                else:
                    kshl_l = kshell_scripts(kshl_dir=kshl_dir, fn_snt=fn_snt_daughter, Nucl=Nucl_daughter, states=bra, hw_truncation=hw_truncation, run_args=run_args)
                    kshl_r = kshell_scripts(kshl_dir=kshl_dir, fn_snt=fn_snt, Nucl=Nucl, states=ket, hw_truncation=hw_truncation, run_args=run_args)
                    kshl_l.run_kshell()
                    kshl_r.run_kshell()
                    if(verbose): print("calculating density: <" + str(i_bra) + "| Density |" + str(i_ket) + ">")
                    trs = transit_scripts(kshl_dir=kshl_dir)
                    fn_den, flip = trs.calc_density(kshl_l, kshl_r, states_list=[lr,], i_wfs=[(i_bra,i_ket),])
                if(flip): Density = TransitionDensity(filename=fn_den[0], Jbra=Jket, wflabel_bra=i_ket, Jket=Jbra, wflabel_ket=i_bra)
                if(not flip): Density = TransitionDensity(filename=fn_den[0], Jbra=Jbra, wflabel_bra=i_bra, Jket=Jket, wflabel_ket=i_ket)
                exp_vals.append(sum(Density.eval(op)))
            return exp_vals

        if(step=="final"):
            exp_vals = []
            for lr in states_list:
                bra = lr[0]
                ket = lr[1]
                if( bra.find("+") != -1 ): Jbra = float( bra.split("+")[0] )
                if( bra.find("-") != -1 ): Jbra = float( bra.split("-")[0] )
                if( ket.find("+") != -1 ): Jket = float( ket.split("+")[0] )
                if( ket.find("-") != -1 ): Jket = float( ket.split("-")[0] )
                if( bra.find("+") != -1 ): i_bra = int( bra.split("+")[1] )
                if( bra.find("-") != -1 ): i_bra = int( bra.split("-")[1] )
                if( ket.find("+") != -1 ): i_ket = int( ket.split("+")[1] )
                if( ket.find("-") != -1 ): i_ket = int( ket.split("-")[1] )
                if(bra == ket and Nucl==Nucl_daughter and fn_snt==fn_snt_daughter):
                    kshl = kshell_scripts(kshl_dir=kshl_dir, fn_snt=fn_snt, Nucl=Nucl, states=bra, hw_truncation=hw_truncation, run_args=run_args)
                    trs = transit_scripts(kshl_dir=kshl_dir)
                    flip = trs.set_filenames(kshl, kshl, states_list=[lr,])
                    fn_den = trs.filenames[lr]
                else:
                    kshl_l = kshell_scripts(kshl_dir=kshl_dir, fn_snt=fn_snt_daughter, Nucl=Nucl_daughter, states=bra, hw_truncation=hw_truncation, run_args=run_args)
                    kshl_r = kshell_scripts(kshl_dir=kshl_dir, fn_snt=fn_snt, Nucl=Nucl, states=ket, hw_truncation=hw_truncation, run_args=run_args)
                    trs = transit_scripts(kshl_dir=kshl_dir)
                    flip = trs.set_filenames(kshl_l, kshl_r, states_list=[lr,])
                    fn_den = trs.filenames[lr]
                if(flip): Density = TransitionDensity(filename=fn_den, Jbra=Jket, wflabel_bra=i_ket, Jket=Jbra, wflabel_ket=i_bra)
                if(not flip): Density = TransitionDensity(filename=fn_den, Jbra=Jbra, wflabel_bra=i_bra, Jket=Jket, wflabel_ket=i_ket)
                exp_vals.append(sum(Density.eval(op)))
            return exp_vals
    def calc_2v_decay(kshl_dir=None,
            fn_snt=None, fn_op=None, Nucl=None, initial_state=None, final_state=None, Nstates_inter=300, hw_truncation=None,
            run_args={"beta_cm":0, "mode_lv_hdd":0}, op_type=-10, op_rankJ=1, op_rankP=1, op_rankZ=1, verbose=False, step="kshell",
            direction="nn->pp", mode="direct", batch_cmd=None, run_cmd=None, Q=0.0, header="", list_prty_gs_inter=[-1,1],
            calc_only_inter=False):

        """
        This would have redundant steps, but easy to run. Do not use for a big run.
        inputs:
            kshel_dir: path to kshell exe files
            fn_snt: file name of snt
            fn_op : file name of operator
            Nucl: parent nuclide
            initial_state: spin and parity of parent nucleus: str like "0+1"
            final_state: spin and parity of daughter nucleus: str like "0+1"
        """
        if(_none_check(kshl_dir, 'kshl_dir')): return
        if(_none_check(fn_snt, 'fn_snt')): return
        if(_none_check(fn_op, 'fn_op')): return
        if(_none_check(Nucl, 'Nucl')): return
        if(_none_check(initial_state, 'initial_state')): return
        if(_none_check(final_state, 'final_state')): return
        gs_candidate_inter = ""
        for prty in list_prty_gs_inter:
            if(prty==-1): gs_candidate_inter += "-1,"
            if(prty== 1): gs_candidate_inter += "+1,"
        gs_candidate_inter = gs_candidate_inter[:-1]
        op = Operator(filename=fn_op, rankJ=op_rankJ, rankP=op_rankP, rankZ=op_rankZ)
        Z_par, N_par, A = _ZNA_from_str(Nucl)
        if(direction=="nn->pp"):
            Z_dau = Z_par + 2
            N_dau = N_par - 2
            Z_int = Z_par + 1
            N_int = N_par - 1
        elif(direction=="pp->nn"):
            Z_dau = Z_par - 2
            N_dau = N_par + 2
            Z_int = Z_par - 1
            N_int = N_par + 1
        Nucl_daughter = "{:s}{:d}".format(PeriodicTable.periodic_table[Z_dau], A)
        Nucl_inter = "{:s}{:d}".format(PeriodicTable.periodic_table[Z_int], A)
        bra = final_state
        ket = initial_state

        if( bra.find("+") != -1 ): Jbra = float( bra.split("+")[0] )
        if( bra.find("-") != -1 ): Jbra = float( bra.split("-")[0] )
        if( ket.find("+") != -1 ): Jket = float( ket.split("+")[0] )
        if( ket.find("-") != -1 ): Jket = float( ket.split("-")[0] )
        if( bra.find("+") != -1 ): i_bra = int( bra.split("+")[1] )
        if( bra.find("-") != -1 ): i_bra = int( bra.split("-")[1] )
        if( ket.find("+") != -1 ): i_ket = int( ket.split("+")[1] )
        if( ket.find("-") != -1 ): i_ket = int( ket.split("-")[1] )
        if( abs(Jbra-Jket) > 2*op_rankJ ):
            print("Error: J={:d} and J={:d} cannot be connected by J=2*{:d} operator".format(Jbra,Jket,op_Jrank))
            return None

        states_list = ""
        if(op_rankP== 1): op_prty="+"
        if(op_rankP==-1): op_prty="-"
        for J in range(int(abs(Jbra-op_rankJ)), int(Jbra+op_rankJ+1)):
            if(not abs(Jket-op_rankJ) <= J <= Jket+op_rankJ): continue
            states_list += "{:d}{:s}{:d},".format(J,op_prty,Nstates_inter)
        states_list = states_list[:-1]
        if(step=="kshell"):
            kshl_l = kshell_scripts(kshl_dir=kshl_dir, fn_snt=fn_snt, Nucl=Nucl_daughter, states=bra, hw_truncation=hw_truncation, run_args=run_args)
            kshl_r = kshell_scripts(kshl_dir=kshl_dir, fn_snt=fn_snt, Nucl=Nucl, states=ket, hw_truncation=hw_truncation, run_args=run_args)
            fn_tmp = "GS_{:s}_{:s}".format(Nucl_inter, os.path.splitext(os.path.basename(fn_snt))[0])
            kshl_inter = kshell_scripts(kshl_dir=kshl_dir, fn_snt=fn_snt, Nucl=Nucl_inter, states=gs_candidate_inter, hw_truncation=hw_truncation, run_args=run_args)
            if(not calc_only_inter):
                kshl_l.run_kshell(batch_cmd=batch_cmd, run_cmd=run_cmd, header=header)
                kshl_r.run_kshell(batch_cmd=batch_cmd, run_cmd=run_cmd, header=header)
                kshl_inter.run_kshell(batch_cmd=batch_cmd, run_cmd=run_cmd, fn_script=fn_tmp)

            kshl_inter = kshell_scripts(kshl_dir=kshl_dir, fn_snt=fn_snt, Nucl=Nucl_inter, states=states_list, hw_truncation=hw_truncation, run_args=run_args)
            if(mode=="direct"): kshl_inter.run_kshell(batch_cmd=batch_cmd,run_cmd=run_cmd, header=header)
            if(mode=="lsf"):
                kshl_inter.run_kshell(batch_cmd=batch_cmd,run_cmd=run_cmd,gen_partition=True,header=header)
                for state in states_list.split(","):
                    if( state.find("+") != -1 ):
                        Jinter = float( state.split("+")[0] )
                        n_inter = int( state.split("+")[1] )
                        prty = "+"
                    if( state.find("-") != -1 ):
                        Jinter = float( state.split("-")[0] )
                        n_inter = int( state.split("-")[1] )
                        prty = "-"
                    kshl_inter.run_kshell_lsf( kshl_r.fn_ptns[ket], kshl_inter.fn_ptns[state], \
                            kshl_r.fn_wfs[ket], kshl_inter.fn_wfs[state], int(2*Jinter), fn_operator=fn_op, \
                            n_vec=Nstates_inter, operator_irank=op_rankJ, operator_iprty=op_rankP, operator_nbody=op_type, \
                            batch_cmd=batch_cmd, run_cmd=run_cmd, header=header)
                    #kshl_inter.run_kshell_lsf( kshl_r.fn_ptns[ket], kshl_inter.fn_ptns[state], \
                    #        kshl_r.fn_wfs[ket], kshl_inter.fn_wfs[state], int(2*Jinter), op="GT", \
                    #        n_vec=Nstates_inter, operator_irank=op_rankJ, operator_iprty=op_rankP,\
                    #        batch_cmd=batch_cmd, run_cmd=run_cmd, header=header)

        elif(step=="density"):
            kshl_l = kshell_scripts(kshl_dir=kshl_dir, fn_snt=fn_snt, Nucl=Nucl_daughter, states=bra, hw_truncation=hw_truncation, run_args=run_args)
            kshl_r = kshell_scripts(kshl_dir=kshl_dir, fn_snt=fn_snt, Nucl=Nucl, states=ket, hw_truncation=hw_truncation, run_args=run_args)
            kshl_inter = kshell_scripts(kshl_dir=kshl_dir, fn_snt=fn_snt, Nucl=Nucl_inter, states=states_list, hw_truncation=hw_truncation, run_args=run_args)
            trs = transit_scripts(kshl_dir=kshl_dir)
            for state in states_list.split(","):
                fn_den_l, flip_l = trs.calc_density(kshl_l, kshl_inter, batch_cmd=batch_cmd, run_cmd=run_cmd, header=header)
                fn_den_r, flip_r = trs.calc_density(kshl_inter, kshl_r, batch_cmd=batch_cmd, run_cmd=run_cmd, header=header)

        elif(step=="eval"):
            kshl_l = kshell_scripts(kshl_dir=kshl_dir, fn_snt=fn_snt, Nucl=Nucl_daughter, states=bra, hw_truncation=hw_truncation, run_args=run_args)
            kshl_r = kshell_scripts(kshl_dir=kshl_dir, fn_snt=fn_snt, Nucl=Nucl, states=ket, hw_truncation=hw_truncation, run_args=run_args)
            kshl_inter = kshell_scripts(kshl_dir=kshl_dir, fn_snt=fn_snt, Nucl=Nucl_inter, states=states_list, hw_truncation=hw_truncation, run_args=run_args)
            trs = transit_scripts(kshl_dir=kshl_dir)
            edict_inter = kshl_inter.summary_to_dictionary()
            levels = sorted(edict_inter.items(), key=lambda x:x[1])
            egs_inter = levels[0][1]
            prt = ""
            reduced_me = 0.0
            for state in states_list.split(","):
                l = (bra,state)
                flip_l = trs.set_filenames(kshl_l, kshl_inter, states_list=[l,])
                fn_den_l = trs.filenames[l]
                r = (state,ket)
                flip_r = trs.set_filenames(kshl_inter, kshl_r, states_list=[r,])
                fn_den_r = trs.filenames[r]
                if( state.find("+") != -1 ):
                    Jinter = float( state.split("+")[0] )
                    n_inter = int( state.split("+")[1] )
                    prty = "+"
                if( state.find("-") != -1 ):
                    Jinter = float( state.split("-")[0] )
                    n_inter = int( state.split("-")[1] )
                    prty = "-"
                if(A%2==0): Jinter_str = str(int(Jinter))
                if(A%2==1): Jinter_str = "{:d}/2".format(int(2*Jinter))
                reduced_me_J = 0.0
                for i_inter in range(1, n_inter+1):
                    if(flip_l): Density_L = TransitionDensity(filename=fn_den_l, Jbra=Jinter, wflabel_bra=i_inter, Jket=Jbra, wflabel_ket=i_bra)
                    if(flip_r): Density_R = TransitionDensity(filename=fn_den_r, Jbra=Jket, wflabel_bra=i_ket, Jket=Jinter, wflabel_ket=i_inter)
                    if(not flip_l): Density_L = TransitionDensity(filename=fn_den_l, Jbra=Jbra, wflabel_bra=i_bra, Jket=Jinter, wflabel_ket=i_inter)
                    if(not flip_r): Density_R = TransitionDensity(filename=fn_den_r, Jbra=Jinter, wflabel_bra=i_inter, Jket=Jket, wflabel_ket=i_ket)
                    me_l = sum(Density_L.eval(op))
                    me_r = sum(Density_R.eval(op))
                    me = me_l * me_r
                    en_inter = edict_inter[(Jinter_str,prty,i_inter)]
                    reduced_me_J += me / ( en_inter-egs_inter + Q)
                    prt += "{:6.1f} {:s} {:6d} {:14.8f} {:14.8f} {:14.8f} {:14.8f}\n".format(Jinter, prty, i_inter, me_l, me_r, en_inter-egs_inter+Q, reduced_me_J)
                reduced_me += reduced_me_J
            return prt
