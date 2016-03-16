import os
import sys
import argparse
import numpy as np
from simdat.openface import oftools
from simdat.core.so import image
from simdat.core import tools
from simdat.core import plot
from simdat.core import ml


class DEMO(oftools.OpenFace):
    def of_init(self):
        """ Init function for child class """

        self.im = image.IMAGE()
        self.io = tools.MLIO()
        self.pl = plot.PLOT()
        self.mpath = None
        self.dbs = None
        self.ml = None
        self.classifier = None

    def set_classifier(self, method):
        """ Set the chosen classifier.
            Need to be called before training, testing and predicting.

        @param method: classification method to be used.
                       Can be RF/Neighbors/SVC

        """
        if method == 'RF':
            self.ml = ml.RFRun(pfs=['ml.json'])
            self.classifier = method
        elif method == 'Neighbors':
            self.ml = ml.NeighborsRun(pfs=['ml.json'])
            self.classifier = method
        else:
            self.ml = ml.SVMRun(pfs=['ml.json'])
            self.classifier = 'SVC'

    def set_dbs(self, dbpath):
        """ Set the dbs. dbs are generated by self.act_rep """

        self.dbs = self.io.find_files(dir_path=dbpath, suffix=('json'))

    def read_model(self, root='./'):
        """ Read the persistent model from pickle file.
            It depends on self.classifier which should be
            set by self.set_classifier. Called by act_predict and act_test

        Keyword arguments:
        root -- the parent directory of the pickle files (default: $PWD)

        """
        self._check_classifier()
        mpath = root + self.classifier + '.pkl'
        if not self.io.check_exist(mpath):
            print('[openface_demo] Error: %s does not exist.' % mpath)
            sys.exit(1)
        return self.ml.read_model(mpath)

    def _pick_imgs(self):
        """ Pick representations of the images
            found in the current directory """

        self._check_dbs()
        return self.pick_reps(self.dbs)

    def _check_dbs(self):
        """ Check if self.dbs are properly set """

        if self.dbs is None or len(self.dbs) == 0:
            print('[openface_demo] Error: No db is found. '
                  'Make sure self.set_dbs(dbpath) ran properly')
            sys.exit(1)

    def _check_classifier(self):
        """ Check if self.ml is properly set """

        if self.ml is None:
            print('[openface_demo] Error: No db is found. '
                  'Make sure self.set_classifier(method=$METHOD) ran properly')
            sys.exit(1)

    def _pca(self, df, ncomp=2, pca_method='PCA'):
        """ Draw for principal component analysis

        @param df: DataFrame of the input data

        Keyword arguments:
        ncomp  -- number or components to be kept (Default: 2)
        method -- method to be used
                  PCA(default)/Randomized/Sparse

        """
        mltl = ml.MLTools()
        res = self.read_df(df, dtype='train', group=False, conv=False)
        p = df['class'].value_counts().idxmax()
        data = res['data']
        fname = p + '_pca.png'
        if ncomp == 1:
            pca_data = mltl.PCA(data, ncomp=1,
                                method=pca_method)
            pca_data = np.array(pca_data).T[0]
            self.pl.histogram(pca_data, fname=fname)
            return p, pca_data
        else:
            pca_data = mltl.PCA(data, method=pca_method)
            pca_data = np.array(pca_data).T
            self.pl.plot_points(pca_data[0], pca_data[1], fname=fname,
                                xmin=-1, xmax=1, ymin=-1, ymax=1)
            return p, [pca_data[0], pca_data[1]]

    def act_reps(self, dir_path=None):
        """ Get facenet representations for images in the current directory.
            The results will be saved to './result.json' You may copy the db
            manually to where self.set_dbs can find.

        Keyword arguments:
        dir_path -- directory of the images to process (default: $PWD)

        """
        images = self.im.find_images(dir_path=dir_path)
        return self.get_reps(images, output=True, class_kwd='')

    def act_train(self):
        """ Training the classifier. This should be done after self.act_reps
            is properly executed, and this function relied the existing
            dbs created by self.act_reps. """

        self._check_classifier()
        df = self._pick_imgs()
        res = self.read_df(df, dtype='train', group=False)
        mf = self.ml.run(res['data'], res['target'])

    def act_pca(self, ncomp=2, mpf='./mapping.json'):

        """ decompose a multivariate dataset in an orthogonal
            set that explain a maximum amount of the variance

        Keyword Arguments:
        ncomp  -- number or components to be kept (Default: 2)
        mpf    -- mapping file of class_from_fath vs real class
                  during training which should be generated
                  by self.act_train.

        """
        print('[openface_demo] ncomp = %i' % ncomp)
        mapping = self.io.parse_json(mpf)
        df = self._pick_imgs()
        all_data = []
        labels = []
        for p in mapping.keys():
            df['class'] = df['class'].astype(type(p))
            _df = df[df['class'] == p]
            if _df.empty:
                continue
            p, data = self._pca(_df, ncomp=ncomp, pca_method='PCA')
            all_data.append(data)
            labels.append(p)
        if ncomp == 1:
            self.pl.plot_1D_dists(all_data, legend=labels)
        else:
            self.pl.plot_classes(all_data, legend=labels)

    def act_predict(self, mpf='./mapping.json',
                    model_root='./', dir_path=None):
        """ Predict based on the trained model

        Keyword Arguments:
        model_root -- parent directory of the model pickle file (default: ./)
        mpf        -- mapping file of class_from_fath vs real class
                      during training which should be generated
                      by self.act_train.
        dir_path   -- parent directory of the images to be predicted

        """
        model = self.read_model(root=model_root)
        res = self.act_reps(dir_path=dir_path)
        mapping = self.io.parse_json(mpf)
        for item in res:
            cl = self.ml.predict(res[item]['rep'], model)['Result'][0]
            print '[openface_demo] Parsing %s' % res[item]['path']
            print [c for c in mapping if mapping[c] == cl][0]

    def act_test(self, mpf='./mapping.json', model_root='./',
                 thre=0.4, matched_out='/www/experiments/'):
        """ Predict based on the trained model

        Keyword Arguments:
        model_root -- parent directory of the model pickle file (default: ./)
        mpf        -- mapping file of class_from_fath vs real class
                      during training which should be generated
                      by self.act_train (default: ./mapping.json)
        thre       -- threshold to be applied to the output probability
                      (default: 0.4)
        matched_out -- where to output images with roi plotted
                       (default: /www/experiments)

        """
        print('[openface_demo] Threshold applied %.2f' % thre)
        from datetime import date
        model = self.read_model(root=model_root)
        df = self._pick_imgs()
        res = self.read_df(df, dtype='test', mpf=mpf, group=True)
        match = 0
        nwrong = 0
        today = date.today().strftime("%Y%m%d")
        new_home = matched_out + today
        for i in range(0, len(res['data'])):
            r1 = self.ml.test(res['data'][i], res['target'][i], model,
                              target_names=res['target_names'])
            cat = res['target'][i][0]
            found = False
            mis_match = False
            if r1['prob'] is None:
                for p in range(0, len(r1['predicted'])):
                    if cat == r1['predicted'][p]:
                        path = res['path'][i]
                        self.pl.patch_rectangle_img(
                            path, res['pos'][i][p],
                            new_name=None)
                        found = True
            else:
                for p in range(0, len(r1['prob'])):
                    prob = r1['prob'][p]
                    vmax = max(prob)
                    imax = prob.argmax()
                    if vmax > thre:
                        if imax == cat:
                            path = res['path'][i]
                            self.pl.patch_rectangle_img(
                                path, res['pos'][i][p],
                                new_home=new_home)
                            found = True
                        else:
                            mis_match = True
            if found:
                match += 1
            if mis_match:
                nwrong += 1
        try:
            print('[openface_demo] Recall = %.2f'
                  % (float(match)/float(len(res['data']))))
            print('[openface_demo] Precision = %.2f'
                  % (float(match)/float(match + nwrong)))
        except:
            pass
        print('[openface_demo] Images with roi are saved to %s' % new_home)


def main():
    parser = argparse.ArgumentParser(
        description="Simple Openface Demo" +
        )
    parser.add_argument(
        "-t", "--test", action='store_true'
        )
    parser.add_argument(
        "-c", "--classifier", type=str, default='SVC',
        help="Classifier to be used SVC(default)/Neighbors/RF"
        )
    parser.add_argument(
        "-p", "--pcut", type=float, default=0.4,
        help="Probability cut to be applied to the classifier" +
             " (default: 0.4, used by action=test)"
        )
    parser.add_argument(
        "-a", "--action", type=str, default='rep',
        help="Action to be taken rep(default)/train/test/predict/pca"
        )
    parser.add_argument(
        "--mpf", type=str, default='./mapping.json',
        help="Path of the mapping file which is generated by action=train" +
             " (default: ./mapping.json, used by action=test/predict/pca)"
        )
    parser.add_argument(
        "--model-path", dest='model_path', type=str, default='./',
        help="Root directory of the model pickle files" +
             " (default: ./ , used by action=test/predict)"
        )
    parser.add_argument(
        "-d", "--dbpath", type=str, default='/www/database/db/',
        help="Path of dbs which are generated by action=rep"
             " (default: /www/database/db/)"
        )
    parser.add_argument(
        "-w", "--workdir", type=str, default=None,
        help="Working directory where the images are stored." +
             " (default: $PWD, used by action=predict)"
        )

    pfs = ['openface.json', 'ml.json']
    args = parser.parse_args()
    demo = DEMO(pfs)
    demo.set_dbs(args.dbpath)

    if args.workdir is None:
        args.workdir = os.getcwd()

    parms = {}

    if args.action == 'rep':
        parms['dir_path'] = args.workdir
    elif args.action == 'pca':
        parms['mpf'] = args.mpf
    elif args.action == 'predict':
        demo.set_classifier(args.classifier)
        parms['mpf'] = args.mpf
        parms['model_root'] = args.model_path
        parms['dir_path'] = args.workdir
    elif args.action == 'test':
        demo.set_classifier(args.classifier)
        parms['thre'] = args.pcut
        parms['mpf'] = args.mpf
        parms['model_root'] = args.model_path
    elif args.action == 'train':
        demo.set_classifier(args.classifier)

    getattr(demo, 'act_' + args.action)(**parms)

if __name__ == '__main__':
    main()
