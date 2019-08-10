import sys
import matplotlib.cm as cm
from . import Nucl

def set_frame(ax, xrng=None, xlab=None):
    ax.set_xticks(xrng)
    ax.set_xticklabels(xlab, rotation=60)
    ax.set_ylabel('Energy (MeV)')

def get_state_color(Jd,P,color_index=None):
    if(color_index == None):
        color_list_p = ['red','salmon','orange','darkgoldenrod','gold','olive',\
                'lime','forestgreen','turquoise','teal','skyblue']
        color_list_n = ['navy','blue','mediumpurple','blueviolet',\
                'mediumorchid','purple','magenta','pink','crimson']
    if(color_index == 1):
        color_list_p = ['red','orange','olive',\
                'lime','forestgreen','turquoise','teal','skyblue']
        color_list_n = ['blue','blueviolet',\
                'mediumorchid','magenta','crimson']
    if(color_index == 2):
        color_list_p = ['red',"k",'orange',\
                'lime','forestgreen','turquoise','teal','skyblue']
        color_list_n = ['blue','blue',\
                'lime','magenta','crimson']
    idx = int(Jd / 2)
    try:
        if(P=="+"): return color_list_p[idx]
        if(P=="-"): return color_list_n[idx]
    except:
        if(P!="+" and P!="-"): print("something wrong (parity)")
        return "k"

def get_energies_dct(summary, absolute = True, snt=None, comment_snt="!"):
    zero_body = 0.0
    edict = {}
    if(snt != None):
        h=Nucl.Op(snt)
        h.read_operator_file(comment_snt)
        zero_body = h.zero
    f = open(summary,'r')
    lines = f.readlines()
    f.close()
    for line in lines:
        data = line.split()
        try:
            N = int(data[0])
            J = data[1]
            P = data[2]
            i = int(data[3])
            e = float(data[5])
            eex = float(data[6])
            if(absolute):
                edict[(J,P,i)] = e + zero_body
            else:
                edict[(J,P,i)] = eex
        except:
            continue
    return edict

def extract_levels(edict, level_list):
    edict2 = {}
    for key in level_list:
        try:
            edict2[key] = edict[key]
        except:
            pass
    return edict2

def ground_state_energy(edict):
    egs = 0.0
    for key in edict.keys():
        egs = min(egs, edict[key])
    return egs

def energies_wrt_ground(edict):
    egs = ground_state_energy(edict)
    edict2 = {}
    for key in edict.keys():
        edict2[key] = edict[key] - egs
    return edict2

def draw_energies(axs, edict, xcenter, width, color=None, color_index=None, lw=4):
    for key in edict.keys():
        try:
            J = int(key[0])*2
        except:
            J = int(key[0][:-2])
        P = key[1]
        i = key[2]
        c = color
        if(c == None): c = get_state_color(J,P, color_index)
        axs.plot([xcenter-width,xcenter+width],[edict[key],edict[key]],c=c,lw=lw)

def draw_connections(axs, ldict, rdict, xleft, xright, color=None, color_index=None, lw=1):
    dct = ldict
    if(len(ldict)>len(rdict)): dct = rdict
    for key in dct.keys():
        if(key in ldict and key in rdict):
            eleft = ldict[key]
            eright = rdict[key]
            c = color
            try:
                J = int(key[0])*2
            except:
                J = int(key[0][:-2])
            if(c == None): c = get_state_color(J,key[1], color_index)
            axs.plot([xleft,xright],[eleft,eright],ls=':',c=c,lw=lw)

def put_JP_auto(axs, dct, x_base, y_thr, xshift):
    eold = 1e20
    x = x_base
    for key in dct.keys():
        try:
            J = int(key[0])*2
        except:
            J = int(key[0][:-2])
        P = key[1]
        i = key[2]
        if(i != 1): continue
        if(abs(eold - dct[key]) < y_thr): x += xshift
        else: x = x_base
        c = get_state_color(J,key[1])
        axs.annotate(str(key[0])+"$^"+P+"$", xy = (x,dct[key]), color =c)
        eold = dct[key]



