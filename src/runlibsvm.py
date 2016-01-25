import os
import subprocess
import argparse
from argparse import ArgumentParser
import numpy as np
from sklearn import metrics
from sklearn.cross_validation import ShuffleSplit, StratifiedShuffleSplit

from Utilities import feval, writingfile, readfeats, getlabels
from FeatureTransformer import feature_transformer


def scaling(dir, emo):
    cmd1 = ["../libSVM/svm-scale", "-l", "-1", "-u", "1", "-s", "../libSVM/"+emo+".range", dir+"/training"]
    with open(dir+"/train.scale", "w") as outfile1:
        subprocess.call(cmd1, stdout=outfile1)
    cmd2 = ["../libSVM/svm-scale", "-r", "../libSVM/"+emo+".range", dir+"/testing"]
    with open(dir+"/test.scale", "w") as outfile2:
        subprocess.call(cmd2, stdout=outfile2)
    outfile1.close()
    outfile2.close()


def predict(ci, gamma, kernel, wi, trfile, tfile, pfile, emo):
    traincmd = ["../libSVM/svm-train", "-c", "0.001", "-t", "2", "-w1", "1", "-w0", "1", "-q", trfile, '../models/all/'+'train.'+emo+'.aux.model']
#    traincmd = ["../libSVM/svm-train", "-c", "0.001", "-t", "2", "-q", trfile]
    traincmd[2] = ci
    traincmd[4] = kernel
#    traincmd[6] = gamma
    traincmd[8] = wi
    subprocess.call(traincmd)
#    model = trfile.split('/')[-1]+'.model'
    model = '../models/all/'+'train.'+emo+'.aux.model'
    predcmd = ["../libSVM/svm-predict", tfile, model, pfile]
    p = subprocess.Popen(predcmd, stdout=subprocess.PIPE)
    output, err = p.communicate()
    return output


def CV(ci, gamma, kernel, wi, trfile, tfile, CV_trfile, CV_tfile, CV_pfile, CV_truey):
    traincmd = ["../libSVM/svm-train", "-c", "0.001", "-t", "2", "-w1", "1", "-w0", "1", "-q", trfile]
    traincmd[2] = ci
    traincmd[4] = kernel
    traincmd[8] = wi
    subprocess.call(traincmd)
    model = trfile.split('/')[-1]+'.model'
    tfeat = readfeats(tfile)
    cv = StratifiedShuffleSplit(y=getlabels(tfeat), n_iter=5, test_size=0.2, random_state=0)
    f1_list = []
    p_list = []
    r_list = []
    count = 0
    for train_index, test_index in cv:
        count += 1
        cv_tfile = CV_tfile+str(count)
        cv_pfile = CV_pfile+str(count)
        cv_truey = CV_truey+str(count)
        X_test = tfeat[test_index]
        y_test = getlabels(X_test)
        writingfile(cv_tfile, X_test)
        writingfile(cv_truey, y_test)
        predcmd = ["../libSVM/svm-predict", cv_tfile, model, cv_pfile]
        p = subprocess.Popen(predcmd, stdout=subprocess.PIPE)
        output, err = p.communicate()
        y_test, y_predicted = feval(cv_truey, cv_pfile)
        p_list.append(metrics.precision_score(y_test, y_predicted, average='binary'))
        r_list.append(metrics.recall_score(y_test, y_predicted, average='binary'))
        f1_list.append(metrics.f1_score(y_test, y_predicted, average='binary'))
    recall = np.mean(np.asarray(r_list))
    precision = np.mean(np.asarray(p_list))
    f1 = np.mean(np.asarray(f1_list))
    print "C=%s, gamma=%s and wi=%s, its F1 is %f"%(ci, gamma, wi, f1)
    return [recall, precision, f1]


def tuneC(trfile, tfile, cv_trfile, cv_tfile, cv_pfile, cv_truey):
    kernel = 2
    c = [1, 10, 30, 50, 100, 0.1, 0.01]
#    gamma = [float(1)/600, 0.0001, 0.00001, 0.1]
    ga = float(1)/600  # though the default gamma value is used
    weights = [0.1, 0.3, 0.5, 0.8, 1, 3, 5, 8, 10]
    tunec = []
    for ci in c:
#        for ga in gamma:
            for wi in weights:
                cv_result = CV(str(ci), str(ga), str(kernel), str(wi), trfile, tfile, cv_trfile, cv_tfile, cv_pfile, cv_truey)
                r = cv_result[0]
                p = cv_result[1]
                f1 = cv_result[-1]
                tunec.append([ci, ga, kernel, wi, r, p, f1])
    tunec = sorted(tunec, key=lambda x: x[-1], reverse=True)
    return tunec


def main(ci, gamma, wi, data_dir, p):
    emotions = [x[1] for x in os.walk(data_dir)][0]
    data_split = "/70-30/"  # define the test data split ratio here and make sure you have the sub folders
    for emo in emotions:
        print 80*"*"
        print "Emotion is", emo
        dir = data_dir+emo
        trainfile = dir+"/train.scale"
        CVtestfile = dir+data_split+emo+".train"
        testfile = dir+data_split+emo+".test"
        predfile = dir+data_split+emo+".test.pred"
        truefile = dir+data_split+emo+".test.true"
        cv_trfile = dir+'/cv/train.cv'
        cv_tfile = dir+'/cv/test.cv'
        cv_pfile = dir+'/cv/predresults.cv'
        cv_truey = dir+'/cv/y_test.cv'

        if 'scale' in p:
            print "---Feature scaling"
            scaling(dir, emo)
        else:
            pass

        if 'tune' in p:
            print "---Parameter tuning"
            tunec = tuneC(trainfile, CVtestfile, cv_trfile, cv_tfile, cv_pfile, cv_truey)
            bestc = tunec[0][0]
            bestgamma = tunec[0][1]
            bestwi = tunec[0][3]
            bestCV = tunec[0][-1]
            print "Tuning: Five-fold CV on %s, the best F1 is %f at c=%s, gamma=%s and wi=%s"%(trainfile, bestCV, str(bestc), str(bestgamma), str(bestwi))

        if ('tune' in p) and ('pred' in p):
            print "---Model fitting and prediction"
            predict(str(bestc), str(bestgamma), str(tunec[0][2]), str(bestwi), trainfile, testfile, predfile, emo)

        if ('tune' not in p) and ('pred' in p):
            print "---Model fitting and prediction"
            print 'C=%s, gamma=%s and wi=%s'%(str(ci), str(gamma), str(wi))
            predict(str(ci), str(gamma), str(2), str(wi), trainfile, testfile, predfile, emo)

        if 'evaluation' in p:
            print "---Evaluation"
            y_test, y_predicted = feval(truefile, predfile)
            print 'Precision score: ', metrics.precision_score(y_test, y_predicted, average='binary')
            print 'Recall score: ', metrics.recall_score(y_test, y_predicted, average='binary')
            print 'F1 score: ', metrics.f1_score(y_test, y_predicted, average='binary')
            print 80*"*"


if __name__ == "__main__":
    parser = ArgumentParser()
    # Please make sure there are 5 sub folders for each emotion within the output folder e.g. test1, provided below:
    parser.add_argument("--d", dest="d", help="Output folder name", default='test1')
    parser.add_argument("--c", dest="ci", help="Penalty parameter, C", default=1)
    parser.add_argument("--w", dest="wi", help="Weight penalty for class 0", default=1)
    parser.add_argument("--gamma", dest="gamma", help="Kernel coefficient parameter, gamma", default=0.01)
    parser.add_argument("--steps", dest="p", help="Choose classification steps: e.g. scale,tune,pred,evaluation or scale,pred,evaluation", default='scale,tune,evaluation')
    args = parser.parse_args()
    data_dir = '../output/'+args.d+'/'

    main(args.ci, args.gamma, args.wi, data_dir, args.p)
