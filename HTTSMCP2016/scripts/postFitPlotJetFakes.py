import CombineHarvester.CombineTools.plotting as plot
import ROOT
import re
import math
import argparse
import json
import numpy as np
import yaml
import sys
import os
import fnmatch
from array import array

ROOT.gROOT.SetBatch(ROOT.kTRUE)
ROOT.TH1.AddDirectory(False)

def getHistogram(fname, histname, dirname='', postfitmode='prefit', allowEmpty=False, logx=False):
    outname = fname.GetName()
    for key in fname.GetListOfKeys():
        histo = fname.Get(key.GetName())
        dircheck = False
        if dirname == '' : dircheck=True
        elif dirname in key.GetName(): dircheck=True
        if isinstance(histo,ROOT.TH1F) and key.GetName()==histname:
            if logx:
                bin_width = histo.GetBinWidth(1)
                xbins = []
                xbins.append(bin_width - 1)
                axis = histo.GetXaxis()
                for i in range(1,histo.GetNbinsX()+1):
                    xbins.append(axis.GetBinUpEdge(i))
                rethist = ROOT.TH1F(histname,histname,histo.GetNbinsX(),array('d',xbins))
                rethist.SetBinContent(1,histo.GetBinContent(1)*(histo.GetBinWidth(1)-(bin_width - 1))/(histo.GetBinWidth(1)))
                rethist.SetBinError(1,histo.GetBinError(1)*(histo.GetBinWidth(1)-(bin_width - 1))/(histo.GetBinWidth(1)))
                for i in range(2,histo.GetNbinsX()+1):
                    rethist.SetBinContent(i,histo.GetBinContent(i))
                    rethist.SetBinError(i,histo.GetBinError(i))
                histo = rethist
            return [histo,outname]
        elif isinstance(histo,ROOT.TDirectory) and postfitmode in key.GetName() and dircheck:
            return getHistogram(histo,histname, allowEmpty=allowEmpty, logx=logx)
    print 'Failed to find %(postfitmode)s histogram with name %(histname)s in file %(fname)s '%vars()
    if allowEmpty:
        return [ROOT.TH1F('empty', '', 1, 0, 1), outname]
    else:
        return None

def signalComp(leg,plots,colour,stacked):
    return dict([('leg_text',leg),('plot_list',plots),('colour',colour),('in_stack',stacked)])

def backgroundComp(leg,plots,colour):
    return dict([('leg_text',leg),('plot_list',plots),('colour',colour)])

def createAxisHists(n,src,xmin=0,xmax=499):
    result = []
    for i in range(0,n):
        res = src.Clone()
        res.Reset()
        res.SetTitle("")
        res.SetName("axis%(i)d"%vars())
        res.SetAxisRange(xmin,xmax)
        res.SetStats(0)
        result.append(res)
    return result

def PositionedLegendUnrolled(width, height, pos, offset):
    o = offset
    w = width
    h = height
    l = ROOT.gPad.GetLeftMargin()
    t = ROOT.gPad.GetTopMargin()
    b = ROOT.gPad.GetBottomMargin()
    r = ROOT.gPad.GetRightMargin()
    if pos == 1:
        return ROOT.TLegend(l + o, 1 - t - o - h, l + o + w, 1 - t - o, '', 'NBNDC')
    if pos == 2:
        c = l + 0.5 * (1 - l - r)
        return ROOT.TLegend(c - 0.5 * w, 1 - t - o - h, c + 0.5 * w, 1 - t - o, '', 'NBNDC')
    if pos == 3:
        return ROOT.TLegend(1 - r - o - w, 1 - t - o - h, 1 - r - o, 1 - t - o, '', 'NBNDC')
    if pos == 4:
        return ROOT.TLegend(l + o, b + o, l + o + w, b + o + h, '', 'NBNDC')
    if pos == 5:
        c = l + 0.5 * (1 - l - r)
        return ROOT.TLegend(c - 0.5 * w, b + o, c + 0.5 * w, b + o + h, '', 'NBNDC')
    if pos == 6:
        return ROOT.TLegend(1 - r - o - w, b + o, 1 - r - o, b + o + h, '', 'NBNDC')
    if pos == 7:
        return ROOT.TLegend(1 - o - w, 1 - t - o - h, 1 - o, 1 - t - o, '', 'NBNDC')

def DrawTitleUnrolled(pad, text, align, scale=1):
    pad_backup = ROOT.gPad
    pad.cd()
    t = pad.GetTopMargin()
    l = pad.GetLeftMargin()
    r = pad.GetRightMargin()

    pad_ratio = (float(pad.GetWh()) * pad.GetAbsHNDC()) / \
        (float(pad.GetWw()) * pad.GetAbsWNDC())
    if pad_ratio < 1.:
        pad_ratio = 1.

    textSize = 0.6
    textOffset = 0.2

    latex = ROOT.TLatex()
    latex.SetNDC()
    latex.SetTextAngle(0)
    latex.SetTextColor(ROOT.kBlack)
    latex.SetTextFont(42)
    latex.SetTextSize(textSize * t * pad_ratio * scale)

    y_off = 1 - t + textOffset * t
    if align == 1:
        latex.SetTextAlign(11)
        latex.DrawLatex(l, y_off, text)
    if align == 2:
        latex.SetTextAlign(21)
        latex.DrawLatex(l + (1 - l - r) * 0.5, y_off, text)
    if align == 3:
        latex.SetTextAlign(31)
        latex.DrawLatex(1 - r, y_off, text)
    pad_backup.cd()

    
def parse_arguments():
    parser = argparse.ArgumentParser()
    #Ingredients when output of PostFitShapes is already provided
    parser.add_argument('--file', '-f',
                    help='Input file if shape file has already been created')
    parser.add_argument('--mA',default='700',
                    help='Signal m_A to plot for model dep')
    parser.add_argument('--tanb',default='30',
                    help='Signal tanb to plot for model dep')
    parser.add_argument('--mPhi',default='700',
                    help='Signal m_Phi to plot for model indep')
    parser.add_argument('--r_ggH',default='0.1',
                    help='Signal ggH XS*BR for model indep')
    parser.add_argument('--r_bbH',default='0.1',
                    help='Signal bbH XS*BR for model indep')
    parser.add_argument('--channel',default='',
                    help='Option to specify channel in case it is not obtainable from the shape file name')
    parser.add_argument('--file_dir',default='',
                    help='Name of TDirectory inside shape file')
    #Ingredients to internally call PostFitShapes
    parser.add_argument('--dir', '-d', 
                    help='Directory for plot (channel-category containing the datacard and workspace)')
    parser.add_argument('--postfitshapes',default=False,
                    action='store_true',help='Run PostFitShapesFromWorkspace')
    parser.add_argument('--workspace',default='mhmodp',
                    help='Part of workspace filename right before .root')
    parser.add_argument('--fitresult',
                    help='Full path to fit result for making post fit plots')
    parser.add_argument('--model_dep',action='store_true',
                    default=False,help='Make plots for full model dependent signal h,H,A')
    parser.add_argument('--mode',default='prefit',
                    help='Prefit or postfit')
    #Blinding options
    parser.add_argument('--manual_blind', action='store_true',
                    default=False,help='Blind data with hand chosen range')
    parser.add_argument('--auto_blind',action='store_true',
                    default=False,help='Blind data automatically based on s/root b')
    parser.add_argument('--auto_blind_check_only',action='store_true',
                    default=False,help='Only print blinding recommendation but still blind data using manual blinding')
    parser.add_argument('--soverb_plot', action='store_true',
                    default=False,help='Make plot with s/root b instead of ratio plot to test what it would blind')
    parser.add_argument('--x_blind_min',default=10000,
                    help='Minimum x for manual blinding')
    parser.add_argument('--x_blind_max',default=4000,
                    help='Maximum x for manual blinding')
    parser.add_argument('--empty_bin_error',action='store_true',
                    default=False, help='Draw error bars for empty bins')
    #General plotting options
    parser.add_argument('--channel_label',default='#mu#tau_{h} no b-tag',
                    help='Channel - category label')
    parser.add_argument('--ratio', default=False,action='store_true',
                    help='Draw ratio plot')
    parser.add_argument('--custom_x_range', action='store_true', 
                    default=False, help='Fix x axis range')
    parser.add_argument('--x_axis_min', default=0.0,
                    help='Fix x axis minimum')
    parser.add_argument('--x_axis_max', default=1000.0, 
                    help='Fix x axis maximum')
    parser.add_argument('--custom_y_range', action='store_true', 
                    default=False, help='Fix y axis range')
    parser.add_argument('--y_axis_min', default=0.001, 
                    help='Fix y axis minimum')
    parser.add_argument('--y_axis_max', default=100.0,
                    help='Fix y axis maximum')
    parser.add_argument('--log_y', action='store_true',
                    help='Use log for y axis')
    parser.add_argument('--log_x', action='store_true',
                    help='Use log for x axis')
    parser.add_argument('--extra_pad', default=0.0, 
                    help='Fraction of extra whitespace at top of plot')
    parser.add_argument('--outname',default='',
                    help='Optional string for start of output filename')
    parser.add_argument('--bkg_fractions', default=False, 
                    action='store_true', help='Instead of yields for each process plot fraction of total bkg in each bin')
    parser.add_argument('--bkg_frac_ratios', default=False, 
                    action='store_true', help='Instead of yields for each process plot fraction of total bkg in each bin')
    parser.add_argument('--uniform_binning', default=False, 
                    action='store_true', help='Make plots in which each bin has the same width') 
    parser.add_argument('--ratio_range',  default="0.7,1.3", 
                    help='y-axis range for ratio plot in format MIN,MAX')
    parser.add_argument('--no_signal', action='store_true',
                    help='Do not draw signal')
    parser.add_argument('--split_y_scale', default=0.0,type=float,
                    help='Use split y axis with linear scale at top and log scale at bottom. Cannot be used together with bkg_frac_ratios')
    parser.add_argument('--sb_vs_b_ratio', action='store_true',
                    help='Draw a Signal + Background / Background into the ratio plot')
    parser.add_argument('--x_title', default='m_{T}^{tot} (GeV)',
                    help='Title for the x-axis')
    parser.add_argument('--y_title', default='dN/dm_{T}^{tot} (1/GeV)',
                    help='Title for the y-axis')
    parser.add_argument('--lumi', default='35.9 fb^{-1} (13 TeV)',
                    help='Lumi label')
    parser.add_argument('--use_asimov', default=True, 
                    action='store_true', help='')

    return parser.parse_args()

def main(args):

    plot.ModTDRStyle(width=1200, height=600, r=0.3, l=0.14, t=0.12,b=0.15)
    ROOT.TGaxis.SetExponentOffset(-0.06, 0.01, "y")
    # Channel & Category label
    bin_number = args.file_dir.split("_")[2]
    if bin_number == "1":
        bin_label = "0-jet"
        plot.ModTDRStyle(r=0.04, l=0.14)
    if bin_number == "2":
        bin_label = "boosted"
    if bin_number == "3":
        bin_label = "dijet loose-m_{jj}"
    if bin_number == "4":
        bin_label = "dijet loose-m_{jj} boosted"
    if bin_number == "5":
        bin_label = "dijet tight-m_{jj}"
    if bin_number == "6":
        bin_label = "dijet tight-m_{jj} boosted"

    if args.channel == '':
        args.channel = args.file_dir.split("_")[1]
    if args.channel == "tt":
        channel_label = "#tau_{h}#tau_{h}"
    if args.channel == "mt":
        channel_label = "#mu_{}#tau_{h}"
    if args.channel == "et":
        channel_label = "#e_{}#tau_{h}"
    if args.channel == "em":
        channel_label = "#e_{}#mu_{}"
        
    ## Add bin labels
    bin_labels = {}
    with open("scripts/bin_labels.yaml", "r") as f:
        try:
            full_bin_labels = yaml.load(f)
            for key, values in full_bin_labels.iteritems():
                if key == args.channel:
                    bin_labels = values[int(bin_number)]
        except yaml.YAMLError as exc:
            print exc

    if bin_number not in ["1","2"]:
        args.x_title = "Bin number"
        Nxbins = 12 #always use 12 sjdphi bins
    elif bin_number in ["2"]:
        args.x_title = "Bin number"
        x_bins = re.split("\[|\]",bin_labels[0])[3].split(",")
        Nxbins = len(x_bins) - 1
    elif bin_number in ["1"]:
        args.x_title = re.split(",|\[|\]", bin_labels[0])[1]
        x_bins = re.split("\[|\]",bin_labels[0])[1].split(",")
        Nxbins = len(x_bins) - 1


    if int(bin_number) > 1:
        # print bin_labels
        y_bin_var = re.split(",|\[|\]", bin_labels[0])[0]
        y_bin_labels = re.split("\[|\]",bin_labels[0])[1].split(",")
        # print y_bin_var
        # print y_bin_labels
    else:
        y_bin_var = ""
        y_bin_labels = ""



    mA = args.mA
    mPhi = args.mPhi
    tb = args.tanb
    r_ggH = args.r_ggH
    r_bbH = args.r_bbH
    workspace = args.workspace
    file_dir = args.file_dir
    fitresult = args.fitresult
    mode = args.mode
    manual_blind = args.manual_blind
    auto_blind = args.auto_blind
    soverb_plot = args.soverb_plot
    auto_blind_check_only = args.auto_blind_check_only
    x_blind_min = args.x_blind_min
    x_blind_max = args.x_blind_max
    empty_bin_error = args.empty_bin_error
    extra_pad = float(args.extra_pad)
    custom_x_range = args.custom_x_range
    custom_y_range = args.custom_y_range
    x_axis_min = float(args.x_axis_min)
    x_axis_max = float(args.x_axis_max)
    y_axis_min = float(args.y_axis_min)
    y_axis_max = float(args.y_axis_max)
    model_dep = args.model_dep
    log_y=args.log_y
    log_x=args.log_x
    fractions=args.bkg_fractions
    frac_ratios=args.bkg_frac_ratios
    split_y_scale=args.split_y_scale
    sb_vs_b_ratio = args.sb_vs_b_ratio
    uniform=args.uniform_binning
    #If plotting bkg fractions don't want to use log scale on y axis
    if fractions:
        log_y = False
    if uniform:
        log_y = False
        log_x = False
    if(args.outname != ''):
        outname=args.outname + '_'
    else:
        outname=''
    
    if args.dir and args.file and not args.postfitshapes:
        print 'Provide either directory or filename, not both'
        sys.exit(1)
    
    if not args.dir and not args.file and not args.postfitshapes:
        print 'Provide one of directory or filename'
        sys.exit(1)
    
    if args.postfitshapes and not args.dir:
        print 'Provide directory when running with --postfitshapes option'
        sys.exit(1)
    
    if manual_blind and auto_blind :
        print 'Pick only one option for blinding strategy out of --manual_blind and --auto_blind'
    #For now, force that one type of blinding is always included! When unblinding the below line will need to be removed
    if not manual_blind and not auto_blind: manual_blind=True    
    
    if (args.auto_blind or args.auto_blind_check_only) and args.model_dep:
        print 'Automated blinding only supported for model independent plots, please use manual blinding'
        sys.exit(1)
    
    if (args.auto_blind or args.auto_blind_check_only) and not args.postfitshapes:
        print 'Option --postfitshapes required when using auto-blinding, to ensure workspaces used for blinding exist in correct format'
        sys.exit(1)
    
    #If call to PostFitWithShapes is requested, this is performed here
    #if args.postfitshapes or soverb_plot:
    if args.postfitshapes:
        print "Internally calling PostFitShapesFromWorkspace on directory ", args.dir
        for root,dirnames,filenames in os.walk(args.dir):
            for filename in fnmatch.filter(filenames, '*.txt.cmb'):
                datacard_file = os.path.join(root,filename) 
            for filename in fnmatch.filter(filenames, '*%(workspace)s.root'%vars()):
                workspace_file = os.path.join(root,filename)
                if model_dep :
                    shape_file=workspace_file.replace('.root','_shapes_mA%(mA)s_tb%(tb)s.root'%vars())
                    shape_file_name=filename.replace ('.root','_shapes_mA%(mA)s_tb%(tb)s.root'%vars())
                else : 
                    shape_file=workspace_file.replace('.root','_shapes_mPhi%(mPhi)s_r_ggH%(r_ggH)s_r_bbH%(r_bbH)s.root'%vars())
                    shape_file_name=filename.replace ('.root','_shapes_mPhi%(mPhi)s_r_ggH%(r_ggH)s_r_bbH%(r_bbH)s.root'%vars()) 
        
        if model_dep is True :
            print "using mA and tanb"
            freeze = 'mA='+mA+',tanb='+tb 
        else: 
            print "using MH="+mPhi+", r_ggH="+r_ggH+" and r_bbH="+r_bbH
            freeze = 'MH='+mPhi+',r_ggH='+r_ggH+',r_bbH='+r_bbH 
        if mode=="postfit": 
            postfit_string = '--fitresult '+fitresult+':fit_s --postfit' 
        else: 
            postfit_string = ''
        print 'PostFitShapesFromWorkspace -d %(datacard_file)s -w %(workspace_file)s -o %(shape_file)s %(postfit_string)s --print --freeze %(freeze)s'%vars()
        os.system('PostFitShapesFromWorkspace -d %(datacard_file)s -w %(workspace_file)s -o %(shape_file)s %(postfit_string)s --print --freeze %(freeze)s'%vars())
    
    
    #Otherwise a shape file with a given naming convention is required
    if not args.postfitshapes:
        if args.dir:
            for root,dirnames,filenames in os.walk(args.dir):
                if model_dep: filestring = '*_shapes_%(mA)s_%(tb)s.root'%vars()
                else: filestring = '*_shapes_mPhi%(mPhi)s_r_ggH%(r_ggH)s_r_bbH%(r_bbH)s.root'%vars()  
                for filename in fnmatch.filter(filenames, '*_shapes_%(mA)s_%(tb)s.root'%vars()):
                    shape_file = os.path.join(root,filename)
        elif args.file:
            print "Providing shape file: ", args.file, ", with specified subdir name: ", file_dir
            shape_file=args.file
            shape_file_name=args.file
    
    histo_file = ROOT.TFile(shape_file)
    
    #Store plotting information for different backgrounds 
    background_schemes = {
        'mt':[
                backgroundComp("t#bar{t}",["TTT"],ROOT.TColor.GetColor(155,152,204)),
                backgroundComp("Electroweak",["VVT"],ROOT.TColor.GetColor(222,90,106)),
                backgroundComp("Z#rightarrow#mu#mu",["ZL","EWKZ"],ROOT.TColor.GetColor(100,192,232)),
                backgroundComp("jet#rightarrow#tau_{h} fakes",["jetFakes"],ROOT.TColor.GetColor(192,232,100)),
                backgroundComp("#mu#rightarrow#tau embedding",["EmbedZTT"],ROOT.TColor.GetColor(248,206,104)),
                backgroundComp("qqH#rightarrow#tau#tau + VH#rightarrow#tau#tau",["qqH_htt125","ZH_htt125","WH_htt125"],ROOT.TColor.GetColor(51,51,255)),
                ],
        'et':[
                backgroundComp("t#bar{t}",["TTT"],ROOT.TColor.GetColor(155,152,204)),
                backgroundComp("Electroweak",["VVT"],ROOT.TColor.GetColor(222,90,106)),
                backgroundComp("Z#rightarrowee",["ZL","EWKZ"],ROOT.TColor.GetColor(100,192,232)),
                backgroundComp("jet#rightarrow#tau_{h} fakes",["jetFakes"],ROOT.TColor.GetColor(192,232,100)),
                backgroundComp("#mu#rightarrow#tau embedding",["EmbedZTT"],ROOT.TColor.GetColor(248,206,104)),
                backgroundComp("qqH#rightarrow#tau#tau + VH#rightarrow#tau#tau",["qqH_htt125","ZH_htt125","WH_htt125"],ROOT.TColor.GetColor(51,51,255)),
                ],
        'tt':[
                backgroundComp("t#bar{t}",["TTT"],ROOT.TColor.GetColor(155,152,204)),
                backgroundComp("Electroweak",["VVT","ZL","EWKZ"],ROOT.TColor.GetColor(222,90,106)),
                backgroundComp("jet#rightarrow#tau_{h} fakes",["jetFakes"],ROOT.TColor.GetColor(192,232,100)),
                backgroundComp("#mu#rightarrow#tau embedding",["EmbedZTT"],ROOT.TColor.GetColor(248,206,104)),
                backgroundComp("qqH#rightarrow#tau#tau + VH#rightarrow#tau#tau",["qqH_htt125","ZH_htt125","WH_htt125"],ROOT.TColor.GetColor(51,51,255)),
                ],
        'em':[
                backgroundComp("t#bar{t}",["TT"],ROOT.TColor.GetColor(155,152,204)),
                backgroundComp("QCD", ["QCD"], ROOT.TColor.GetColor(250,202,255)),
                backgroundComp("Electroweak",["VV","W"],ROOT.TColor.GetColor(222,90,106)),
                backgroundComp("Z#rightarrowll",["ZLL"],ROOT.TColor.GetColor(100,192,232)),
                backgroundComp("#mu#rightarrow#tau embedding",["EmbedZTT"],ROOT.TColor.GetColor(248,206,104)),
                backgroundComp("qqH#rightarrow#tau#tau + VH#rightarrow#tau#tau",["qqH_htt125","ZH_htt125","WH_htt125"],ROOT.TColor.GetColor(51,51,255)),
                ]
        }
    
    #Extract relevent histograms from shape file
    [sighist,binname] = getHistogram(histo_file,'TotalSig', file_dir, mode, args.no_signal, log_x)
    sighist_ggH = getHistogram(histo_file,'ggHsm_htt',file_dir, mode, args.no_signal, log_x)[0]
    sbhist = getHistogram(histo_file,'TotalProcs',file_dir, mode, args.no_signal, log_x)[0]
    # bkg_sb_vs_b_ratio_hist = getHistogram(histo_file,'TotalBkg',file_dir, mode, logx=log_x)[0]
    for i in range(0,sighist.GetNbinsX()):
        if sighist.GetBinContent(i) < y_axis_min: sighist.SetBinContent(i,y_axis_min)
    bkghist = getHistogram(histo_file,'TotalBkg',file_dir, mode, logx=log_x)[0]
    
    if not args.use_asimov:
        total_datahist = getHistogram(histo_file,"data_obs",file_dir, mode, logx=log_x)[0]
    else:
        total_datahist = getHistogram(histo_file,"TotalBkg",file_dir, mode, logx=log_x)[0].Clone()
        total_sighist = getHistogram(histo_file,"TotalSig",file_dir, mode, logx=log_x)[0].Clone()
        total_datahist.Add(total_sighist)
        for bin_ in range(1,total_datahist.GetNbinsX()+1):
            content = total_datahist.GetBinContent(bin_)
            total_datahist.SetBinError(bin_, np.sqrt(content))


    binerror_datahist = total_datahist.Clone()
    blind_datahist = total_datahist.Clone()
    total_datahist.SetMarkerStyle(20)
    blind_datahist.SetMarkerStyle(20)
    blind_datahist.SetLineColor(1)
    
    #Blinding by hand using requested range, set to 200-4000 by default
    if manual_blind or auto_blind_check_only:
        for i in range(0,total_datahist.GetNbinsX()):
            low_edge = total_datahist.GetBinLowEdge(i+1)
            high_edge = low_edge+total_datahist.GetBinWidth(i+1)
            if ((low_edge > float(x_blind_min) and low_edge < float(x_blind_max)) or (high_edge > float(x_blind_min) and high_edge<float(x_blind_max))):
                blind_datahist.SetBinContent(i+1,-0.1)
                blind_datahist.SetBinError(i+1,0)
    
    #Set bin errors for empty bins if required:
    if empty_bin_error:
        for i in range (1,blind_datahist.GetNbinsX()+1):
            if blind_datahist.GetBinContent(i) == 0:
                blind_datahist.SetBinError(i,1.8)
    
    if uniform:
        blind_datahist2 = ROOT.TH1F(blind_datahist.GetName(),blind_datahist.GetName(),blind_datahist.GetNbinsX(),0,blind_datahist.GetNbinsX())
        total_datahist2 = ROOT.TH1F(total_datahist.GetName(),total_datahist.GetName(),total_datahist.GetNbinsX(),0,total_datahist.GetNbinsX())
        bkghist2 = ROOT.TH1F(bkghist.GetName(),bkghist.GetName(),bkghist.GetNbinsX(),0,bkghist.GetNbinsX())
        for i in range(0,blind_datahist.GetNbinsX()):
            blind_datahist2.SetBinContent(i,blind_datahist.GetBinContent(i))
            blind_datahist2.SetBinError(i,blind_datahist.GetBinError(i))
            total_datahist2.SetBinContent(i,total_datahist.GetBinContent(i))
            total_datahist2.SetBinError(i,total_datahist.GetBinError(i))
        blind_datahist = blind_datahist2
        total_datahist = total_datahist2
        for i in range(0,bkghist.GetNbinsX()):
            bkghist2.SetBinContent(i,bkghist.GetBinContent(i))
            bkghist2.SetBinError(i,bkghist.GetBinError(i))
        bkghist = bkghist2
    
    #Normalise by bin width 
    blind_datahist.Scale(1.0,"width")
    total_datahist.Scale(1.0,"width")
    sighist.Scale(1.0,"width")
    
    channel = args.channel
    if channel == '':  channel=binname[4:6]
    
    #Create stacked plot for the backgrounds
    bkg_histos = []
    bkg_histos_fractions = []
    for i,t in enumerate(background_schemes[channel]):
        plots = t['plot_list']
        h = ROOT.TH1F()
        for j,k in enumerate(plots):
            if h.GetEntries()==0 and getHistogram(histo_file,k, file_dir,mode,logx=log_x) is not None:
                if not uniform:
                    h = getHistogram(histo_file,k, file_dir,mode, logx=log_x)[0]
                else :
                    htemp = getHistogram(histo_file,k,file_dir, mode,logx=log_x)[0]
                    h = ROOT.TH1F(k,k,htemp.GetNbinsX(),0,htemp.GetNbinsX())
                    for bp in range(0,htemp.GetNbinsX()):
                        h.SetBinContent(bp+1,htemp.GetBinContent(bp+1))
                        h.SetBinError(bp+1,htemp.GetBinError(bp+1))
                h.SetName(k)
            else:
                if getHistogram(histo_file,k, file_dir,mode, logx=log_x) is not None:
                    if not uniform:
                        h.Add(getHistogram(histo_file,k, file_dir,mode,logx=log_x)[0])
                    else :
                        htemp = getHistogram(histo_file,k,file_dir, mode,logx=log_x)[0]
                        htemp2 = ROOT.TH1F(k,k,htemp.GetNbinsX(),0,htemp.GetNbinsX())
                        for bp in range(0,htemp.GetNbinsX()):
                            htemp2.SetBinContent(bp+1,htemp.GetBinContent(bp+1))
                            htemp2.SetBinError(bp+1,htemp.GetBinError(bp+1))
                        h.Add(htemp2)
        h.SetFillColor(t['colour'])
        h.SetLineColor(ROOT.kBlack)
        h.SetMarkerSize(0)
        
        if not soverb_plot and not fractions and not uniform : h.Scale(1.0,"width")
        if fractions:
            for i in range(1,h.GetNbinsX()+1) :
                h.SetBinContent(i,h.GetBinContent(i)/bkghist.GetBinContent(i))
        if frac_ratios:
            h_frac = h.Clone()
            for i in range(1, h_frac.GetNbinsX()+1):
                h_frac.SetBinContent(i,h_frac.GetBinContent(i)/bkghist.GetBinContent(i))
            bkg_histos_fractions.append(h_frac)
        bkg_histos.append(h)
    
    stack = ROOT.THStack("hs","")
    for hists in bkg_histos:
        stack.Add(hists)
    
    if frac_ratios:
        stack_frac = ROOT.THStack("hs_frac","")
        for hists in bkg_histos_fractions:
            stack_frac.Add(hists)
    
    
    #Setup style related things
    c2 = ROOT.TCanvas()
    c2.cd()
    
    if args.ratio:
        if frac_ratios:
            pads=plot.MultiRatioSplit([0.25,0.14],[0.01,0.01],[0.01,0.01])
        elif split_y_scale:
            pads=plot.ThreePadSplit(0.53,0.29,0.01,0.01)
        else:
            pads=plot.TwoPadSplit(0.29,0.01,0.01)
    else:
        pads=plot.OnePad()
    pads[0].cd()
    if(log_y):
        if split_y_scale:
            pads[2].SetLogy(1)
        else:
            pads[0].SetLogy(1)
    if(log_x):
        pads[0].SetLogx(1)
        if(split_y_scale):
            pads[2].SetLogx(1)
    
    if custom_x_range:
            if x_axis_max > bkghist.GetXaxis().GetXmax(): x_axis_max = bkghist.GetXaxis().GetXmax()
    if args.ratio and not fractions:
        if not frac_ratios:
            if(log_x): 
                pads[1].SetLogx(1)
            axish = createAxisHists(2,bkghist,bkghist.GetXaxis().GetXmin(),bkghist.GetXaxis().GetXmax()-0.01)
            axish[1].GetXaxis().SetTitle(args.x_title)
            if file_dir.split("_")[2] not in  ["1","2"]:
                axish[1].GetXaxis().SetLabelSize(0.03)
                axish[1].GetXaxis().SetTitleSize(0.04)
            axish[1].GetYaxis().SetNdivisions(4)
            # if soverb_plot: 
            #     axish[1].GetYaxis().SetTitle("S/#sqrt(B)")
            # elif split_y_scale or sb_vs_b_ratio: 
            #     axish[1].GetYaxis().SetTitle("")
            # else: 
            #     axish[1].GetYaxis().SetTitle("Obs/Exp")
            #axish[1].GetYaxis().SetTitleSize(0.04)
            axish[1].GetYaxis().SetLabelSize(0.033)
            axish[1].GetXaxis().SetLabelSize(0.033)
            print bkghist.GetNbinsX()
            print bkghist.GetNbinsX()/Nxbins
            axish[1].GetXaxis().SetNdivisions(bkghist.GetNbinsX()/Nxbins,Nxbins,0,False)
            # axish[1].GetYaxis().SetTitleOffset(1.3)
            axish[0].GetYaxis().SetTitleSize(0.048)
            axish[0].GetYaxis().SetLabelSize(0.033)
            axish[0].GetYaxis().SetTitleOffset(0.6)
            axish[0].GetXaxis().SetTitleSize(0)
            axish[0].GetXaxis().SetLabelSize(0)
            axish[0].GetXaxis().SetNdivisions(bkghist.GetNbinsX()/Nxbins,Nxbins,0,False)
            axish[0].GetXaxis().SetRangeUser(x_axis_min,bkghist.GetXaxis().GetXmax()-0.01)
            axish[1].GetXaxis().SetRangeUser(x_axis_min,bkghist.GetXaxis().GetXmax()-0.01)
            axish[0].GetXaxis().SetMoreLogLabels()
            axish[0].GetXaxis().SetNoExponent()
            axish[1].GetXaxis().SetMoreLogLabels()
            axish[1].GetXaxis().SetNoExponent()
    
            if custom_x_range:
                axish[0].GetXaxis().SetRangeUser(x_axis_min,x_axis_max-0.01)
                axish[1].GetXaxis().SetRangeUser(x_axis_min,x_axis_max-0.01)
            if custom_y_range:
                axish[0].GetYaxis().SetRangeUser(y_axis_min,y_axis_max)
                axish[1].GetYaxis().SetRangeUser(y_axis_min,y_axis_max)
            if split_y_scale:
                axistransit=split_y_scale
                axish.append(axish[0].Clone())
    
                axish[0].SetMinimum(axistransit)
                axish[0].SetTickLength(0)
    
                axish[2].GetYaxis().SetRangeUser(y_axis_min, axistransit)
                axish[2].GetYaxis().SetTitle("")
                axish[2].GetYaxis().SetLabelSize(0.033)
                axish[2].GetYaxis().SetNdivisions(3)
                width_sf = ((1-pads[0].GetTopMargin())-pads[0].GetBottomMargin())/((1-pads[2].GetTopMargin())-pads[2].GetBottomMargin())
                axish[2].GetYaxis().SetTickLength(width_sf*axish[0].GetYaxis().GetTickLength())
    
        else :
            if(log_x):
                pads[1].SetLogx(1)
                pads[2].SetLogx(1) 
            axish = createAxisHists(3,bkghist,bkghist.GetXaxis().GetXmin(),bkghist.GetXaxis().GetXmax()-0.01)
            axish[1].GetXaxis().SetTitle(args.x_title)
            axish[1].GetYaxis().SetNdivisions(4)
            axish[2].GetXaxis().SetTitle(args.x_title)
            axish[2].GetYaxis().SetNdivisions(4)
            axish[1].GetYaxis().SetTitleSize(0.03)
            axish[1].GetYaxis().SetLabelSize(0.03)
            axish[1].GetYaxis().SetTitleOffset(1.7)
            axish[2].GetYaxis().SetTitleOffset(1.7)
            axish[2].GetYaxis().SetTitleSize(0.03)
            axish[2].GetYaxis().SetLabelSize(0.03)
            axish[1].GetYaxis().SetTitle("Bkg. frac.")
            axish[2].GetYaxis().SetTitle("Obs/Exp")
            axish[0].GetXaxis().SetTitleSize(0)
            axish[0].GetXaxis().SetLabelSize(0)
            axish[1].GetXaxis().SetTitleSize(0)
            axish[1].GetXaxis().SetLabelSize(0)
            axish[0].GetXaxis().SetRangeUser(x_axis_min,bkghist.GetXaxis().GetXmax()-0.01)
            axish[1].GetXaxis().SetRangeUser(x_axis_min,bkghist.GetXaxis().GetXmax()-0.01)
            if custom_x_range:
                axish[0].GetXaxis().SetRangeUser(x_axis_min,x_axis_max-0.01)
                axish[1].GetXaxis().SetRangeUser(x_axis_min,x_axis_max-0.01)
                axish[2].GetXaxis().SetRangeUser(x_axis_min,x_axis_max-0.01)
            if custom_y_range:
                axish[0].GetYaxis().SetRangeUser(y_axis_min,y_axis_max)
    else:
        axish = createAxisHists(1,bkghist,bkghist.GetXaxis().GetXmin(),bkghist.GetXaxis().GetXmax()-0.01)
    #  axish[0].GetYaxis().SetTitleOffset(1.4)
        if custom_x_range:
            axish[0].GetXaxis().SetRangeUser(x_axis_min,x_axis_max-0.01)
        if custom_y_range and not fractions:
            axish[0].GetYaxis().SetRangeUser(y_axis_min,y_axis_max)
        elif fractions: axish[0].GetYaxis().SetRangeUser(0,1)
    axish[0].GetYaxis().SetTitle("Events/bin")
    # elif soverb_plot: 
    #     axish[0].GetYaxis().SetTitle("Events")
    # elif fractions: 
    #     axish[0].GetYaxis().SetTitle("Fraction of total bkg")
    axish[0].GetXaxis().SetTitle(args.x_title)
    if not custom_y_range: axish[0].SetMaximum(extra_pad*bkghist.GetMaximum())
    if not custom_y_range: 
        if(log_y): axish[0].SetMinimum(0.0009)
        else: axish[0].SetMinimum(0)
    
    hist_indices = [0,2] if split_y_scale else [0]
    for i in hist_indices:
        pads[i].cd()
        axish[i].Draw("AXIS")
    
        #Draw uncertainty band
        bkghist.SetFillColor(plot.CreateTransparentColor(12,0.4))
        bkghist.SetLineColor(0)
        bkghist.SetMarkerSize(0)
    
        stack.Draw("histsame")
        #Don't draw total bkgs/signal if plotting bkg fractions
        if not fractions and not uniform:
            bkghist.Draw("e2same")
            #Add signal, either model dependent or independent
            if not args.no_signal and ((split_y_scale and i == 2) or (not split_y_scale)):
                sighist.SetLineColor(ROOT.kRed)
                sighist.SetLineWidth(2)
                # A trick to remove vertical lines for the signal histogram at the borders while preventing the lines to end in the middle of the plot.
                for j in range(1,sighist.GetNbinsX()+1):
                    entry = sighist.GetBinContent(j)
                    if split_y_scale:
                        if entry < axish[2].GetMinimum():
                            sighist.SetBinContent(j,axish[2].GetMinimum()*1.00001)
                    else:
                        if entry < axish[0].GetMinimum():
                            sighist.SetBinContent(j,axish[0].GetMinimum()*1.00001)
                sighist.Draw("histsame][") # removing vertical lines at the borders of the pad; possible with the trick above
        blind_datahist.DrawCopy("e0x0same")
        axish[i].Draw("axissame")
    
    pads[0].cd()
    pads[0].SetTicks(1)
    #Setup legend
    if file_dir.split("_")[2] == "1":
        legend = plot.PositionedLegend(0.30,0.30,3,0.03)
    else:
        legend = PositionedLegendUnrolled(0.13,0.45,7,0.02)
    legend.SetTextFont(42)
    legend.SetTextSize(0.025)
    legend.SetFillStyle(0)
    
    if not soverb_plot and not fractions: legend.AddEntry(total_datahist,"Observation","PE")
    #Drawn on legend in reverse order looks better
    bkg_histos.reverse()
    background_schemes[channel].reverse()
    for legi,hists in enumerate(bkg_histos):
        legend.AddEntry(hists,background_schemes[channel][legi]['leg_text'],"f")
    legend.AddEntry(bkghist,"Background uncertainty","f")
    legend.AddEntry(sighist,"ggH#rightarrow#tau#tau (#alpha=0, #mu_{ggH}^{#tau#tau}=1)"%vars(),"l")
    legend.Draw("same")

    latex2 = ROOT.TLatex()
    latex2.SetNDC()
    latex2.SetTextAngle(0)
    latex2.SetTextColor(ROOT.kBlack)
    latex2.SetTextFont(42)
    if bin_number == "1":
        latex2.SetTextSize(0.04)
        latex2.DrawLatex(0.145,0.955,"{} {}".format(channel_label, bin_label))
    else:
        latex2.SetTextAlign(23)
        latex2.SetTextSize(0.033)
        latex2.DrawLatex(0.46,0.927,"{} {}".format(channel_label, bin_label))

    #CMS and lumi labels
    plot.FixTopRange(pads[0], plot.GetPadYMax(pads[0]), extra_pad if extra_pad>0 else 0.30)
    if bin_number == "1":
        plot.DrawCMSLogo(pads[0], 'CMS', 'Preliminary', 11, 0.045, 0.05, 1.0, '', 1.0)
        plot.DrawTitle(pads[0], args.lumi, 3)
    else:
        plot.DrawCMSLogo(pads[0], 'CMS', 'Preliminary', 0, 0.07, -0.1, 2.0, '', 0.4)
        DrawTitleUnrolled(pads[0], args.lumi, 3, scale=0.5)
    
    #Add ratio plot if required
    if args.ratio and not soverb_plot and not fractions:
        ratio_bkghist = plot.MakeRatioHist(bkghist,bkghist,True,False)
        sbhist.SetLineColor(ROOT.kRed)
        sbhist.SetLineWidth(2)
        ratio_sighist = plot.MakeRatioHist(sbhist,bkghist,True,False)
        blind_datahist = plot.MakeRatioHist(blind_datahist,bkghist,True,False)
        # if sb_vs_b_ratio:
        #     ratio_sbhist = plot.MakeRatioHist(sbhist,bkg_sb_vs_b_ratio_hist,True,False)
        pads[1].cd()
        pads[1].SetGrid(0,1)
        axish[1].Draw("axis")
        axish[1].SetMinimum(float(args.ratio_range.split(',')[0]))
        axish[1].SetMaximum(float(args.ratio_range.split(',')[1]))
        ratio_bkghist.SetMarkerSize(0)
        ratio_bkghist.Draw("e2same")
        ratio_sighist.Draw("histsame")
        # if sb_vs_b_ratio:
        #     ratio_sbhist.SetMarkerSize(0)
        #     ratio_sbhist.SetLineColor(ROOT.kGreen+3)
        #     ratio_sbhist.SetLineWidth(3)
        #     ratio_sbhist.Draw("histsame][")
        blind_datahist.DrawCopy("e0x0same")
        pads[1].RedrawAxis("G")
        # if split_y_scale or sb_vs_b_ratio:
            # Add a ratio legend for y-splitted plots or plots with sb vs b ratios
        rlegend = ROOT.TLegend(0.85, 0.27, 0.98, 0.16, '', 'NBNDC')
        rlegend.SetTextFont(42)
        rlegend.SetTextSize(0.025)
        rlegend.SetFillStyle(0)
        rlegend.AddEntry(blind_datahist,"Obs/Bkg","PE")
        rlegend.AddEntry(ratio_sighist,"(Sig+Bkg)/Bkg","L")
        # if sb_vs_b_ratio:
        #     rlegend.AddEntry(ratio_sbhist,"(Sig+Bkg)/Bkg","L")
        rlegend.Draw("same")
        # Draw extra axis for explanation (use "N" for no optimisation)
        if int(bin_number) > 2:
            extra_axis = ROOT.TGaxis(0,-0.8,Nxbins,-0.8,-3.2,3.2,304,"NS");
            extra_axis.SetLabelSize(0.025)
            extra_axis.SetLabelFont(42)
            extra_axis.SetMaxDigits(2)
            extra_axis.SetTitle("#Delta#phi_{jj}")
            extra_axis.SetTitleSize(0.033)
            extra_axis.SetTitleOffset(1.1)
            extra_axis.SetTickSize(0.08)
            extra_axis.Draw()
        
    # if soverb_plot:
    #     pads[1].cd()
    #     pads[1].SetGrid(0,1)
    #     axish[1].Draw("axis")
    #     axish[1].SetMinimum(0)
    #     axish[1].SetMaximum(10)
    #     if model_dep:
    #         sighist_forratio.SetLineColor(2)
    #         sighist_forratio.Draw("same")
    #     else:
    #         sighist_ggH_forratio.SetLineColor(ROOT.kBlue)
    #         sighist_ggH_forratio.Draw("same")
    #         sighist_bbH_forratio.SetLineColor(ROOT.kBlue+3)
    #         sighist_bbH_forratio.Draw("same")
    
    pads[0].cd()
    pads[0].GetFrame().Draw()
    if not split_y_scale:
            pads[0].RedrawAxis()

    # Add lines after every 12 bins for dijet bins
    # Need a fix for boosted category!
    line = ROOT.TLine()
    line.SetLineWidth(2)
    line.SetLineStyle(2)
    line.SetLineColor(ROOT.kBlack)
    x = bkghist.GetNbinsX()/Nxbins
    if int(bin_number) > 1:
        for l in range(1,x):
            pads[0].cd()
            ymax = axish[0].GetMaximum()
            ymin = axish[0].GetMinimum()
            line.DrawLine(l*Nxbins,ymin,l*Nxbins,ymax)
            if args.ratio:
                pads[1].cd()
                ymax = axish[1].GetMaximum()
                ymin = axish[1].GetMinimum()
                line.DrawLine(l*Nxbins,ymin,l*Nxbins,ymax)
    
    ## Add bin labels between lines
    pads[0].cd()
    latex_bin = ROOT.TLatex()
    latex_bin.SetNDC()
    latex_bin.SetTextAngle(0)
    latex_bin.SetTextColor(ROOT.kBlack)
    latex_bin.SetTextFont(42)
    latex_bin.SetTextSize(0.028)
    if len(y_bin_labels) > 5: 
        latex_bin.SetTextSize(0.023)
    print len(y_bin_labels)
    
    for i in range(0, len(y_bin_labels)):
        if i < len(y_bin_labels)-1:
            y_bin_label = "{} #leq {} < {} {}".format(y_bin_labels[i],y_bin_var,y_bin_labels[i+1],"GeV")
            xshift = 0.76/len(y_bin_labels)*i
            latex_bin.DrawLatex(0.095+xshift,0.82,y_bin_label)
        else:
            y_bin_label = "        {} > {} {}".format(y_bin_var,y_bin_labels[i],"GeV")
            xshift = 0.76/len(y_bin_labels)*i
            latex_bin.DrawLatex(0.095+xshift,0.82,y_bin_label)
    
    #Save as png and pdf with some semi sensible filename
    shape_file_name = shape_file_name.replace(".root","_%(mode)s"%vars())
    shape_file_name = shape_file_name.replace("_shapes","")
    outname += shape_file_name+"_"+file_dir.strip("htt").strip("_")
    if soverb_plot : outname+="_soverb"
    if(log_y): outname+="_logy"
    if(log_x): outname+="_logx"
    c2.SaveAs("%(outname)s.png"%vars())
    c2.SaveAs("%(outname)s.pdf"%vars())

if __name__ == "__main__":
    args = parse_arguments()
    main(args)
    
