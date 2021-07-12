#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NOTE: use svm_main_pbs instead of this function. Because we run svm analysis on the cluster. svm_main_pbs is the most updated version of svm code.

Run svm_init.py to set vars needed here.

Performs SVM analysis on a particular experiment of a session.
Saves the results in: dir_svm = '/allen/programs/braintv/workgroups/nc-ophys/Farzaneh'
    if using same_num_neuron_all_planes, results will be saved in: dir_svm/ 'same_num_neurons_all_planes'


Created on Fri Aug  2 15:24:17 2019
@author: farzaneh
"""

from def_funs import *
from def_funs_general import *
from svm_funs import *

    
#%%
def svm_main(session_id, experiment_ids, validity_log_all, dir_svm, frames_svm, numSamples, saveResults, use_ct_traces, same_num_neuron_all_planes=0):

    
    #%% Set SVM vars
    
#    same_num_neuron_all_planes = 1 # if 1, use the same number of neurons for all planes to train svm
    svm_min_neurs = 3 # min population size for training svm

#    frames_svm = np.arange(-10, 30) #30 # run svm on how what frames relative to omission
#    numSamples = 3 #10 #50
#    saveResults = 1    
    
    svmn = 'svm_gray_omit'
        
    kfold = 10
    regType = 'l2'
    
    norm_to_max_svm = 1 # normalize each neuron trace by its max
    doPlots = 0 # svm regularization plots
    
    softNorm = 1 # soft normalziation : neurons with sd<thAct wont have too large values after normalization
    thAct = 5e-4 # will be used for soft normalization #1e-5 
    # you did soft normalization when using inferred spikes ... i'm not sure if it makes sense here (using df/f trace); but we should take care of non-active neurons: 
    # Set NsExcluded : Identify neurons that did not fire in any of the trials (during ep) and then exclude them. Otherwise they cause problem for feature normalization.
    
    smallestC = 0   
    shuffleTrs = False # set to 0 so for each iteration of numSamples, all frames are trained and tested on the same trials# If 1 shuffle trials to break any dependencies on the sequence of trails 
    # note about shuffleTrs: if you wanted to actually take effect, you should copy the relevant part from the svm code (svm_omissions) to
    # here before you go through nAftOmit frames ALSO do it for numSamples so for each sample different set of testing and training 
    # trials are used, however, still all nAftOmit frames use the same set ... 
    #... in the current version, the svm is trained and tested on different trials 
    # I don't think it matters at all, so I am not going to change it!
    cbest0 = np.nan
    useEqualTrNums = np.nan
    cbestKnown = 0 #cbest = np.nan
    
                        
    #%% Set initial vars
    
    # %matplotlib inline
    #get_ipython().magic(u'matplotlib inline')
    
    # To align on omissions, get 40 frames before omission and 39 frames after omission
    samps_bef = 40 
    samps_aft = 40
    
#    num_planes = 8
        
    svm_total_frs = len(frames_svm)
    
    now = (datetime.datetime.now()).strftime("%Y%m%d_%H%M%S")
    
    cols = np.array(['session_id', 'experiment_id', 'mouse_id', 'date', 'cre', 'stage', 'area', 'depth', 'n_omissions', 'n_neurons', 'traces_aveTrs_time_ns', 'traces_aveNs_time_trs', 'peak_amp_eachN_traceMed', 'peak_timing_eachN_traceMed', 'peak_amp_trs_ns', 'peak_timing_trs_ns', 'peak_h1', 'peak_h2', 'auc_peak_h1_h2'])
    
    if same_num_neuron_all_planes:        
        cols_svm = ['frames_svm', 'thAct', 'numSamples', 'softNorm', 'regType', 'cvect', 'meanX_allFrs', 'stdX_allFrs', 
               'cbest_allFrs', 'w_data_allFrs', 'b_data_allFrs',
               'perClassErrorTrain_data_allFrs', 'perClassErrorTest_data_allFrs',
               'perClassErrorTest_shfl_allFrs', 'perClassErrorTest_chance_allFrs',
               'inds_subselected_neurons_all', 'population_sizes_to_try', 'numShufflesN']
        
    else:    
        cols_svm = ['frames_svm', 'thAct', 'numSamples', 'softNorm', 'regType', 'cvect', 'meanX_allFrs', 'stdX_allFrs', 
               'cbest_allFrs', 'w_data_allFrs', 'b_data_allFrs',
               'perClassErrorTrain_data_allFrs', 'perClassErrorTest_data_allFrs',
               'perClassErrorTest_shfl_allFrs', 'perClassErrorTest_chance_allFrs',
               'testTrInds_allSamps_allFrs', 'Ytest_allSamps_allFrs', 'Ytest_hat_allSampsFrs_allFrs']
           
        
    
    #%% Load some important variables from the experiment
    
#    [whole_data, data_list, table_stim] = load_session_data(session_id) # data_list is similar to whole_data but sorted by area and depth
    [whole_data, data_list, table_stim, behav_data] = load_session_data_new(session_id, experiment_ids, use_ct_traces)
    
    
    #%% Set number of neurons for all planes
    # Do this if training svm on the same number of neurons on all planes
    
    if same_num_neuron_all_planes==1:
        
        num_neurons_all_planes = [] # for invalid experiments it will be nan.
    
        for index, lims_id in enumerate(data_list['lims_id']):    
            '''
            for il in [7]: #range(num_planes):
                index = il
                lims_id = data_list['lims_id'].iloc[il]
            '''
            ##%% Abort the analysis if the experiment is invalid        
            if validity_log_all.iloc[validity_log_all.lims_id.values == int(lims_id)]['valid'].bool() == False: # we dont realy need this. because in svm_init, we only use valid experiment ids... so data_list here has only the valid experiment ids.
                num_neurons = np.nan
            else:            
                local_fluo_traces = whole_data[lims_id]['fluo_traces'] # neurons x frames
                num_neurons = local_fluo_traces.shape[0]    
            
            num_neurons_all_planes.append(num_neurons)
                    
        min_num_neurons_all_planes = np.nanmin(num_neurons_all_planes)
        nN_trainSVM = np.max([svm_min_neurs, min_num_neurons_all_planes]) # use the same number of neurons for all planes to train svm
        
        # Train SVM on the following population sizes
        population_sizes_to_try = [nN_trainSVM] # [x+1 for x in range(X0.shape[0])] : if you want to try all possible population sizes

        print('Number of neurons per plane: %s' %str(sorted(num_neurons_all_planes)))
        print('Training SVM on the following population sizes for all planes: %s neurons.' %str(population_sizes_to_try))
        
    
    #%%
    exp_ids = list(whole_data.keys())
    mouse = whole_data[exp_ids[0]]['mouse']
    date = whole_data[exp_ids[0]]['experiment_date']    
    cre = whole_data[exp_ids[0]]['cre'] # it will be the same for all lims_ids (all planes in a session)
    stage = whole_data[exp_ids[0]]['stage']
    
    # start time of omissions (in sec)
    list_omitted = table_stim[table_stim['omitted']==True]['start_time']
    list_omitted0 = list_omitted + 0
    # start time of all flashes (in sec)
    list_flashes = table_stim['start_time'].values #[table_stim['omitted']==False]['start_time']
    
    
    #%% Make sure the session has omission trials
    
    if len(list_omitted)==0:
#        sess_no_omission.append(session_id)
        sys.exit('Aborting analysis as there are no omission trials in session %d!' %session_id)
        

    #%% Check for "weird" cases: repeated omissions (based on start times) or consecutive omissions
    #s = np.sort(np.diff(list_omitted))
    #si = np.argsort(np.diff(list_omitted))
    
    d = np.diff(list_omitted0)
    # If there are any repeated omissions, remove one of them.
    rep_om = np.argwhere(d == 0).flatten()
    list_omitted.iloc[rep_om] = np.nan
    
    # consecutive omission: would be interesting to study them but for now remove them all.    
    a = np.argwhere(np.logical_and(d>0 , d<.8)).flatten()
    consec_om = np.sort(np.concatenate((a, a+1), axis=0)) # remove any flash that is preceded or followed by another omitted flash
    list_omitted.iloc[consec_om] = np.nan
    
    # remove the values set to nan
    #list_omitted.drop(list_omitted.index[consec_om, rep_om])
    list_omitted = list_omitted[~np.isnan(list_omitted.values)]                
#        len(list_omitted0), len(list_omitted)
#        list_omitted0, ist_omitted
    
    
    #%% Loop through the 8 planes of each session
    
    this_sess = pd.DataFrame([], columns = cols)  #        local_time_traces_all = [] #        depth_all = [] #        area_all = []
#    print(data_list['lims_id'].values)
    for index, lims_id in enumerate(data_list['lims_id']):    
        ''' 
        for il in [0]: #range(num_planes):
            index = il
            lims_id = data_list['lims_id'].iloc[il]
        '''        
        '''
        ll = list(enumerate(data_list['lims_id'])); 
        l = ll[0]; # first plane
        index = l[0]; # plane index
        lims_id = l[1] # experiment id 
        '''
        
        print('\n======================== Analyzing experiment %s, plane %d/%d ========================\n' %(lims_id, index+1, num_planes))

        depth = whole_data[lims_id]['imaging_depth']
        area = whole_data[lims_id]['targeted_structure']
    
        this_sess.at[index, cols[range(8)]] = session_id, lims_id, mouse, date, cre, stage, area, depth


        #%% Abort the analysis if the experiment is invalid
        
        if validity_log_all.iloc[validity_log_all.lims_id.values == int(lims_id)]['valid'].bool() == False: # we dont realy need this. because in svm_init, we only use valid experiment ids... so data_list here has only the valid experiment ids.
            print('Skipping invalid experiment %d' %int(lims_id))
            this_sess.at[index, :] = np.nan # check this works.
            sys.exit()
           
            
        #%% Continue the analysis only on valid experiments
           
        local_fluo_traces = whole_data[lims_id]['fluo_traces'] # neurons x frames
        local_time_traces = whole_data[lims_id]['time_trace']  # frame times in sec. Volume rate is 10 Hz. Are these the time of frame onsets?? (I think yes... double checking with Jerome/ Marina.)

        num_neurons = local_fluo_traces.shape[0]

        frame_dur = np.mean(np.diff(local_time_traces)) # difference in sec between frames
        print(f'Frame duration {frame_dur} ms')
        if np.logical_or(frame_dur < .9, frame_dur > .1):
            print(f'\n\nWARNING:Frame duration is unexpected!! {frame_dur}ms\n\n')
        
        # Convert peak_win to frames (new way to code list_times)
#                frame_dur = np.mean(np.diff(local_time_traces)) # difference in sec between frames
        # compute peak_win_frames, ie window to look for peak in frame units
#                peak_win_frames = samps_bef + np.floor(peak_win / frame_dur).astype(int)
#                list_times = np.arange(peak_win_frames[0], peak_win_frames[-1]+1)
        
#            local_time_traces_all.append(local_time_traces)
#            depth_all.append(depth)
#            area_all.append(area)
        
        """
        # plot the trace of all neurons (for the entire session) and mark the flash onsets
        plt.figure(figsize=(12,7)); 
        plt.plot(local_time_traces, local_fluo_traces.T); 
        plt.vlines(list_flashes, 0, 4); 
        plt.xlim([900,950])
        """
                
        
        #%% Align on omission trials
                
        # Keep a matrix of omission-aligned traces for all neurons and all omission trials    
        local_fluo_allOmitt = np.full((samps_bef + samps_aft, num_neurons, len(list_omitted)), np.nan) # time x neurons x omissions_trials 
        local_time_allOmitt = np.full((samps_bef + samps_aft, len(list_omitted)), np.nan) # time x omissions_trials

        # Loop over omitted trials to align traces on omissions
        flashes_win_trace_all = []
        flashes_win_trace_index_all = []
        num_omissions = 0 # trial number
        
        for indiv_time in list_omitted: # indiv_time = list_omitted.iloc[0]
            
            local_index = np.argmin(np.abs(local_time_traces - indiv_time)) # the index of omission on local_time_traces               
            
            be = local_index - samps_bef
            af = local_index + samps_aft
            
            if ~np.logical_and(be >= 0 , af <= local_fluo_traces.shape[1]): # make sure the omission is at least samps_bef frames after trace beigining and samps_aft before trace end. 
                print('Omission at time %f cannot be analyzed: %d timepoints before it and %d timepoints after it!' %(indiv_time, be, af)) 
                
                
            try:
                # Align on omission
                local_fluo_allOmitt[:,:, num_omissions] = local_fluo_traces[:, be:af].T # frame x neurons x omissions_trials (10Hz)
                # local_time_allOmitt is frame onset relative to omission onset. (assuming that the times in local_time_traces are frame onsets.... still checking on this, but it seems to be the rising edge, hence frame onset time!)
                # so local_time_allOmitt will be positive if omission onset is before frame onset.
                local_time_allOmitt[:, num_omissions] = local_time_traces[be:af] - indiv_time # frame x omissions_trials
                
                # Identify the flashes (time and index on local_time_allOmitt) that happened within local_time_allOmitt                    
                flashes_relative_timing = list_flashes - indiv_time # timing of all flashes in the session relative to the current omission
                # the time of flashes that happened within the omit-aligned trace
                a = np.logical_and(flashes_relative_timing >= local_time_allOmitt[0, num_omissions], flashes_relative_timing <= local_time_allOmitt[-1, num_omissions]) # which flashes are within local_time
                flashes_win_trace = flashes_relative_timing[a] 
                # now find the index of flashes_win_trace on local_time_allOmitt
                a = [np.argmin(np.abs(local_time_allOmitt[:, num_omissions] - flashes_win_trace[i])) for i in range(len(flashes_win_trace))]
                flashes_win_trace_index = a # the index of omission on local_time_traces
                """
                plt.plot(local_time_allOmitt[:,num_omissions], local_fluo_allOmitt[:,:,num_omissions])
                plt.vlines(flashes_win_trace, -.4, .4)

                plt.plot(local_fluo_allOmitt[:,:,num_omissions])
                plt.vlines(flashes_win_trace_index, -.4, .4)
                """
                num_omissions = num_omissions + 1
                flashes_win_trace_all.append(flashes_win_trace)
                flashes_win_trace_index_all.append(flashes_win_trace_index)
                
#                    time 0 (omissions) values:
#                    local_fluo_allOmitt[samps_bef,:,:]
#                    local_time_allOmitt[samps_bef,:]
                
            except Exception as e:
                print(indiv_time, num_omissions, be, af, local_index)
                print(e)
                                    
                                        
        # remove the last nan rows from the traces, which happens if some of the omissions are not used for alignment (due to being too early or too late in the session) 
        if len(list_omitted)-num_omissions > 0:
            local_fluo_allOmitt = local_fluo_allOmitt[:,:,0:-(len(list_omitted)-num_omissions)]
            local_time_allOmitt = local_time_allOmitt[:,0:-(len(list_omitted)-num_omissions)]


        local_fluo_allOmitt0_orig = local_fluo_allOmitt + 0      
#                local_fluo_allOmitt = local_fluo_allOmitt0_orig 
                            
        print('%d neurons; %d omission trials' %(num_neurons, num_omissions))
        this_sess.at[index, ['n_omissions', 'n_neurons']] = num_omissions, num_neurons
        

        #%%#############################################################
        ###### The following two variables are the key variables: ######
        ###### (they are ready to be used)                        ######
        ###### calcium traces aligned on omissions:               ######
        ###### local_fluo_allOmitt  (frames x units x trials)     ######
        ###### and their time traces:                             ######
        ###### local_time_allOmitt  (frames x trials)             ######
        ################################################################
        
        
        #%%
        if num_omissions < 10:
            sys.exit('Too few trials to do SVM training! omissions=%d' %(num_omissions))
        
        if np.logical_and(same_num_neuron_all_planes , num_neurons < svm_min_neurs):
            sys.exit('Too few neurons to do SVM training! neurons=%d' %(num_neurons))

        
        #%% Normalize each neuron trace by its max (so if on a day a neuron has low FR in general, it will not be read as non responsive!)
        
        if norm_to_max_svm==1:
            # compute max on the entire trace of the session:
            aa_mx = np.max(local_fluo_traces, axis=1) # neurons
            
            a = np.transpose(local_fluo_allOmitt, (0,2,1)) # frames x trials x units
            b = a / aa_mx
            local_fluo_allOmitt = np.transpose(b, (0,2,1)) # frames x units x trials
        
        
        #%% Starting to set variables for the SVM analysis                
        
        meanX_allFrs = np.full((svm_total_frs, num_neurons), np.nan)
        stdX_allFrs = np.full((svm_total_frs, num_neurons), np.nan)        
        
        if same_num_neuron_all_planes:
            nnt = num_neurons #X_svm[0]
            numShufflesN = np.ceil(nnt/float(nN_trainSVM)).astype(int) # if you are selecting only 1 neuron out of 500 neurons, you will do this 500 times to get a selection of all neurons. On the other hand if you are selecting 400 neurons out of 500 neurons, you will do this only twice.

            perClassErrorTrain_data_allFrs = np.full((len(population_sizes_to_try), numShufflesN, numSamples, svm_total_frs), np.nan)        
            perClassErrorTest_data_allFrs = np.full((len(population_sizes_to_try), numShufflesN, numSamples, svm_total_frs), np.nan)
            perClassErrorTest_shfl_allFrs = np.full((len(population_sizes_to_try), numShufflesN, numSamples, svm_total_frs), np.nan)
            perClassErrorTest_chance_allFrs = np.full((len(population_sizes_to_try), numShufflesN, numSamples, svm_total_frs), np.nan)
            if nN_trainSVM==1:
                w_data_allFrs = np.full((len(population_sizes_to_try), numShufflesN, numSamples, nN_trainSVM, svm_total_frs), np.nan).squeeze() # squeeze helps if num_neurons=1 
            else:
                w_data_allFrs = np.full((len(population_sizes_to_try), numShufflesN, numSamples, nN_trainSVM, svm_total_frs), np.nan) # squeeze helps if num_neurons=1 
            b_data_allFrs = np.full((len(population_sizes_to_try), numShufflesN, numSamples, svm_total_frs), np.nan)
            
            cbest_allFrs = np.full((len(population_sizes_to_try), numShufflesN, svm_total_frs), np.nan)
            
            
        ##########################
        else:
            perClassErrorTrain_data_allFrs = np.full((numSamples, svm_total_frs), np.nan)        
            perClassErrorTest_data_allFrs = np.full((numSamples, svm_total_frs), np.nan)
            perClassErrorTest_shfl_allFrs = np.full((numSamples, svm_total_frs), np.nan)
            perClassErrorTest_chance_allFrs = np.full((numSamples, svm_total_frs), np.nan)
            if num_neurons==1:
                w_data_allFrs = np.full((numSamples, num_neurons, svm_total_frs), np.nan).squeeze() # squeeze helps if num_neurons=1 
            else:
                w_data_allFrs = np.full((numSamples, num_neurons, svm_total_frs), np.nan) # squeeze helps if num_neurons=1 
            b_data_allFrs = np.full((numSamples, svm_total_frs), np.nan)
        
            cbest_allFrs = np.full(svm_total_frs, np.nan)
            
            
            
        numTrials = 2*local_fluo_allOmitt.shape[2]   # numDataPoints = X_svm.shape[1] # trials             
        len_test = numTrials - int((kfold-1.)/kfold*numTrials) # number of testing trials   
        numDataPoints = numTrials
        
        if len_test==1:
            Ytest_hat_allSampsFrs_allFrs = np.full((numSamples, len_test, svm_total_frs), np.nan).squeeze() # squeeze helps if len_test=1
        else:
            Ytest_hat_allSampsFrs_allFrs = np.full((numSamples, len_test, svm_total_frs), np.nan)
        Ytest_allSamps_allFrs = np.full((numSamples, len_test, svm_total_frs), np.nan)         
        testTrInds_allSamps_allFrs = np.full((numSamples, len_test, svm_total_frs), np.nan)
           
        ifr = -1

        
        #%% Use SVM to classify population activity on the gray-screen frame right before the omission vs. the activity on frame + nAftOmit after omission 
        
        for nAftOmit in frames_svm: #range(frames_after_omission):
            ifr = ifr+1
            print('\n================ Running SVM on frame %d relative to omission ================\n' %nAftOmit)
            
            # x
            g = local_fluo_allOmitt[samps_bef - 1,:,:] # units x trials ; neural activity in the frame before the omission (gray screen)
            m = local_fluo_allOmitt[samps_bef + nAftOmit,:,:] # units x trials ; neural activity on the frame of omission
            
            # y
            g_y = np.zeros(g.shape[1])
            m_y = np.ones(m.shape[1])
            
            # now set the x matrix for svm
            X_svm = np.concatenate((g, m), axis=1) # units x (gray + omission)
            Y_svm = np.concatenate((g_y, m_y)) # trials (gray + omission)
            
            
            #%% Z score (make each neuron have mean 0 and std 1 across all trials)
            
            # mean and std of each neuron across all trials (trials here mean both gray screen frames and omission frames)
            m = np.mean(X_svm, axis=1)
            s = np.std(X_svm, axis=1)
                                
            meanX_allFrs[ifr,:] = m # frs x neurons
            stdX_allFrs[ifr,:] = s     
            
            # soft normalziation : neurons with sd<thAct wont have too large values after normalization                    
            if softNorm==1:
                s = s + thAct     
        
            X_svm = ((X_svm.T - m) / s).T # units x trials
                                            
                            
            #%% ############################ Run SVM analysis #############################
            
            if same_num_neuron_all_planes:
                perClassErrorTrain_nN_all, perClassErrorTest_nN_all, wAllC_nN_all, bAllC_nN_all, cbestAllFrs_nN_all, cvect, \
                        perClassErrorTest_shfl_nN_all, perClassErrorTest_chance_nN_all, inds_subselected_neurons_all, numShufflesN \
                = set_best_c_diffNumNeurons(X_svm,Y_svm,regType,kfold,numDataPoints,numSamples,population_sizes_to_try,doPlots,useEqualTrNums,smallestC,shuffleTrs,cbest0,\
                             fr2an=np.nan, shflTrLabs=0, X_svm_incorr=0, Y_svm_incorr=0, mnHRLR_acrossDays=np.nan)
                
            else:
                perClassErrorTrain, perClassErrorTest, wAllC, bAllC, cbestAll, cbest, cvect,\
                        perClassErrorTestShfl, perClassErrorTestChance, testTrInds_allSamps, Ytest_allSamps, Ytest_hat_allSampsFrs0, trsnow_allSamps \
                = set_best_c(X_svm,Y_svm,regType,kfold,numDataPoints,numSamples,doPlots,useEqualTrNums,smallestC,shuffleTrs,cbest0,\
                             fr2an=np.nan, shflTrLabs=0, X_svm_incorr=0, Y_svm_incorr=0, mnHRLR_acrossDays=np.nan) # outputs have size the number of shuffles in setbestc (shuffles per c value)
                
            
            ########## Set the SVM output at best C (for all samples)
            
            if same_num_neuron_all_planes:
                for i_pop_size in range(len(population_sizes_to_try)):
                    
                    for inN in range(numShufflesN):
                        # each element of perClassErrorTrain_nN_all is for a neural population of a given size. 
                        # perClassErrorTrain_nN_all[0] has size: # numShufflesN x nSamples x nCvals
                        perClassErrorTrain = perClassErrorTrain_nN_all[i_pop_size][inN] 
                        perClassErrorTest = perClassErrorTest_nN_all[i_pop_size][inN]
                        perClassErrorTestShfl = perClassErrorTest_shfl_nN_all[i_pop_size][inN]
                        perClassErrorTestChance = perClassErrorTest_chance_nN_all[i_pop_size][inN]
                        wAllC = wAllC_nN_all[i_pop_size][inN] # each element of wAllC_nN_all has size: numShufflesN x nSamples x nCvals x nNerons_used_for_training
                        bAllC = bAllC_nN_all[i_pop_size][inN]
                        cbest = cbestAllFrs_nN_all[i_pop_size][inN]
                        
                        indBestC = np.squeeze([0 if cbestKnown else np.in1d(cvect, cbest)])
                                                
                        perClassErrorTrain_data = perClassErrorTrain[:,indBestC].squeeze()
                        perClassErrorTest_data = perClassErrorTest[:,indBestC].squeeze()
                        perClassErrorTest_shfl = perClassErrorTestShfl[:,indBestC].squeeze()
                        perClassErrorTest_chance = perClassErrorTestChance[:,indBestC].squeeze()
                        w_data = wAllC[:,indBestC,:].squeeze() # samps x neurons
                        b_data = bAllC[:,indBestC].squeeze()
                                
                        
                        ########## keep SVM vars for all frames after omission 
                        cbest_allFrs[i_pop_size,inN,ifr] = cbest
                        
                        perClassErrorTrain_data_allFrs[i_pop_size,inN,:,ifr] = perClassErrorTrain_data # numSamps        
                        perClassErrorTest_data_allFrs[i_pop_size,inN,:,ifr] = perClassErrorTest_data
                        perClassErrorTest_shfl_allFrs[i_pop_size,inN,:,ifr] = perClassErrorTest_shfl
                        perClassErrorTest_chance_allFrs[i_pop_size,inN,:,ifr] = perClassErrorTest_chance
                        if num_neurons==1:
                            w_data_allFrs[i_pop_size,inN,:,ifr] = w_data # numSamps x neurons
                        else:
                            w_data_allFrs[i_pop_size,inN,:,:,ifr] = w_data # numSamps x neurons
                        b_data_allFrs[i_pop_size,inN,:,ifr] = b_data            

            
            ################################################
            else:   
                
                indBestC = [0 if cbestKnown else np.in1d(cvect, cbest)]
    #                for ifr in range(nFrs):   
#                if cbestKnown:
#                    indBestC = 0
#                else:
#                    indBestC = np.in1d(cvect, cbest)
                    
                perClassErrorTrain_data = perClassErrorTrain[:,indBestC].squeeze()
                perClassErrorTest_data = perClassErrorTest[:,indBestC].squeeze()
                perClassErrorTest_shfl = perClassErrorTestShfl[:,indBestC].squeeze()
                perClassErrorTest_chance = perClassErrorTestChance[:,indBestC].squeeze()
                w_data = wAllC[:,indBestC,:].squeeze() # samps x neurons
                b_data = bAllC[:,indBestC].squeeze()
                Ytest_hat_allSampsFrs = Ytest_hat_allSampsFrs0[:,indBestC,:].squeeze()
    
                
                ########## keep SVM vars for all frames after omission 
                cbest_allFrs[ifr] = cbest
                
                perClassErrorTrain_data_allFrs[:,ifr] = perClassErrorTrain_data # numSamps        
                perClassErrorTest_data_allFrs[:,ifr] = perClassErrorTest_data
                perClassErrorTest_shfl_allFrs[:,ifr] = perClassErrorTest_shfl
                perClassErrorTest_chance_allFrs[:,ifr] = perClassErrorTest_chance
                if num_neurons==1:
                    w_data_allFrs[:,ifr] = w_data # numSamps x neurons
                else:
                    w_data_allFrs[:,:,ifr] = w_data # numSamps x neurons
                b_data_allFrs[:,ifr] = b_data            
                Ytest_hat_allSampsFrs_allFrs[:,:,ifr] = Ytest_hat_allSampsFrs # numSamps x numTestTrs
                
                Ytest_allSamps_allFrs[:,:,ifr] = Ytest_allSamps # numSamps x numTestTrs                                        
                testTrInds_allSamps_allFrs[:,:,ifr] = testTrInds_allSamps  # numSamps x numTestTrs
    #                    trsnow_allSamps_allFrs = trsnow_allSamps                    
                
                '''
                a_train = np.mean(perClassErrorTrain, axis=0)
                a_test = np.mean(perClassErrorTest, axis=0)
                a_shfl = np.mean(perClassErrorTestShfl, axis=0)
                a_chance = np.mean(perClassErrorTestChance, axis=0)
                
                plt.figure()
                plt.plot(a_train, color='k', label='train') 
                plt.plot(a_test, color='r', label='test') 
                plt.plot(a_shfl, color='y', label='shfl')
                plt.plot(a_chance, color='b', label='chance')
                plt.legend(loc='center left', bbox_to_anchor=(1, .7))
                plt.ylabel('% Classification error')
                plt.xlabel('C values')
                '''                       
                #### Sanity checks ####
                # the following two are the same:
    #                (abs(Ytest_hat_allSampsFrs[0] - Y_svm[testTrInds_allSamps[0].astype(int)])).mean()
    #                perClassErrorTest_data[0]
    
                # the following two are the same:
    #                Ytest_allSamps[2]
    #                Y_svm[testTrInds_allSamps[2].astype(int)]

        
    
    
        #%% Save SVM vars (for each experiment separately)
        ####################################################################################################################################                
        
        #%%                
        svm_vars = pd.DataFrame([], columns = np.concatenate((cols[range(10)], cols_svm)))
        
        # experiment info
        svm_vars.at[index, cols[range(10)]] = this_sess.iloc[index, range(10)] 
        
        # svm output
        if same_num_neuron_all_planes:
            svm_vars.at[index, cols_svm] = frames_svm, thAct, numSamples, softNorm, regType, cvect, meanX_allFrs, stdX_allFrs, \
                cbest_allFrs, w_data_allFrs, b_data_allFrs, \
                perClassErrorTrain_data_allFrs, perClassErrorTest_data_allFrs, \
                perClassErrorTest_shfl_allFrs, perClassErrorTest_chance_allFrs, \
                inds_subselected_neurons_all, population_sizes_to_try, numShufflesN
            
        else:
            svm_vars.at[index, cols_svm] = frames_svm, thAct, numSamples, softNorm, regType, cvect, meanX_allFrs, stdX_allFrs, \
                cbest_allFrs, w_data_allFrs, b_data_allFrs, \
                perClassErrorTrain_data_allFrs, perClassErrorTest_data_allFrs, \
                perClassErrorTest_shfl_allFrs, perClassErrorTest_chance_allFrs, \
                testTrInds_allSamps_allFrs, Ytest_allSamps_allFrs, Ytest_hat_allSampsFrs_allFrs
                  
            
        #%% Save SVM results
        
        cre_now = cre[:cre.find('-')]
        # mouse, session, experiment: m, s, e
        if same_num_neuron_all_planes:
            name = '%s_m-%d_s-%d_e-%s_%s_sameNumNeuronsAllPlanes_%s' %(cre_now, mouse, session_id, lims_id, svmn, now)
        else:
            name = '%s_m-%d_s-%d_e-%s_%s_%s' %(cre_now, mouse, session_id, lims_id, svmn, now) 
        
        if saveResults:
            print('Saving .h5 file')
            svmName = os.path.join(dir_svm, name + '.h5') # os.path.join(d, svmn+os.path.basename(pnevFileName))
            print(svmName)
            # Save to a h5 file                    
            svm_vars.to_hdf(svmName, key='svm_vars', mode='w')
            

#%%                    
            '''
            # save arrays to h5:
            with h5py.File(svmName, 'w') as f:                        
                f.create_dataset('svm_vars', data=svm_vars)
#                    for k, v in svm_vars.items(): # a = list(svm_vars.items()); k = a[0][0]; v = a[0][1]
#                        f.create_dataset(k, data=v)                      
            f.close()
            '''
            
            # read h5 file                    
#                    svm_vars = pd.read_hdf(svmName, key='svm_vars')                    
            '''
            f = h5py.File(svmName, 'r')                    
            for k, v in f.items(): # a = list(f.items()); k = a[0][0]; v = np.asarray(a[0][1])
                exec(k + ' = np.asarray(v)')                        
            f.close()
            '''                                         
#                    scio.savemat(svmName, save_dict)
        
            
        ## Make dictionaries ... (I couldnt save them as h5 file)
        '''
        # define sess_info (similar to this_sess but as a dict ... to save it with other SVM vars below:
        
        k = this_sess.columns
        v = this_sess.iloc[index,:]                
        sess_info = dict()                
        for i in range(10):                
            sess_info[k[i]] = v[i]

        # define SVM vars as a dictionary
        svm_vars = {'thAct':thAct, 'numSamples':numSamples, 'softNorm':softNorm, 'regType':regType, 'cvect':cvect, #'smallestC':smallestC, 'cbestAll':cbestAll, 'cbest':cbest,
               'meanX_allFrs':meanX_allFrs, 'stdX_allFrs':stdX_allFrs, #'eventI_ds':eventI_ds, 
               'cbest_allFrs':cbest_allFrs, 'w_data_allFrs':w_data_allFrs, 'b_data_allFrs':b_data_allFrs,
               'perClassErrorTrain_data_allFrs':perClassErrorTrain_data_allFrs,
               'perClassErrorTest_data_allFrs':perClassErrorTest_data_allFrs,
               'perClassErrorTest_shfl_allFrs':perClassErrorTest_shfl_allFrs,
               'perClassErrorTest_chance_allFrs':perClassErrorTest_chance_allFrs,
               'testTrInds_allSamps_allFrs':testTrInds_allSamps_allFrs, 
               'Ytest_allSamps_allFrs':Ytest_allSamps_allFrs,
               'Ytest_hat_allSampsFrs_allFrs':Ytest_hat_allSampsFrs_allFrs}
        '''                        
            
            
#%%
"""
get_ipython().magic(u'matplotlib inline')

# read the svm_vars file
a = pd.read_hdf(svmName, key='svm_vars')
   
# make plots
a_train = np.mean(a.iloc[0]['perClassErrorTrain_data_allFrs'], axis=0)
a_test = np.mean(a.iloc[0]['perClassErrorTest_data_allFrs'], axis=0)
a_shfl = np.mean(a.iloc[0]['perClassErrorTest_shfl_allFrs'], axis=0)
a_chance = np.mean(a.iloc[0]['perClassErrorTest_chance_allFrs'], axis=0)

plt.figure()
plt.plot(a_train, color='k', label='train') 
plt.plot(a_test, color='r', label='test') 
plt.plot(a_shfl, color='y', label='shfl')
plt.plot(a_chance, color='b', label='chance')
plt.legend(loc='center left', bbox_to_anchor=(1, .7))                
plt.ylabel('% Classification error')
plt.xlabel('Frame after omission')  
"""



