import dataclasses
import hashlib
import json
import threading
import unittest
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler,OneHotEncoder
from sklearn.feature_selection import RFE,SequentialFeatureSelector
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import KFold
from l7_analysis import AnalysisConfig,run_analysis,predict_artifact
from l7_analysis.config import Guard,InputError
from l7_analysis.preprocessing import FrameEncoder
from l7_analysis.selection import rfe_path,sfs_path,folds_for


class AnalysisTests(unittest.TestCase):
    def data(self,n=90):
        rng=np.random.default_rng(45);X=rng.normal(size=(n,4))
        d=pd.DataFrame(X,columns=['a','b','c','d']);d['y']=3*X[:,0]-2*X[:,2]+rng.normal(scale=.2,size=n)
        return d
    def config(self,**kw):
        return AnalysisConfig(target='y',outer_folds=3,inner_folds=3,methods=('ols',),**kw)

    def test_fold_encoding_matches_independent_sklearn(self):
        train=pd.DataFrame({'n':[0.,2.,np.nan,4.],'c':['a','b',None,'a']})
        validation=pd.DataFrame({'n':[1000.,np.nan],'c':['unseen','b']})
        enc=FrameEncoder().fit(train)
        reference=make_pipeline(ColumnTransformer([
          ('n',SimpleImputer(strategy='median'),['n']),
          ('c',make_pipeline(SimpleImputer(strategy='most_frequent',missing_values=None),
                            OneHotEncoder(drop='first',handle_unknown='ignore',sparse_output=False)),['c'])]),StandardScaler())
        reference.fit(train)
        np.testing.assert_allclose(enc.transform(validation)[0],reference.transform(validation))
        self.assertEqual(enc.fields[0]['fill'],2.)
        self.assertEqual(enc.transform(validation)[1]['unknown_categories'],{'c':1})

    def test_constant_and_all_missing_fields_reported(self):
        d=pd.DataFrame({'x':[1.,2.,3.],'constant':[4.,4.,4.],'empty':[np.nan]*3,'cat':[None]*3})
        e=FrameEncoder().fit(d);z,_=e.transform(d)
        self.assertEqual(z.shape,(3,1));self.assertEqual(len(e.dropped_constant),2)
        self.assertEqual(sum(f['all_missing_training'] for f in e.fields),2)
        np.testing.assert_allclose(z.mean(axis=0),0,atol=1e-12)
        np.testing.assert_allclose(z.std(axis=0),1)

    def test_json_encoding_round_trip_and_semantic_keys(self):
        d=pd.DataFrame({'a:b':['x:y','z','x:y'],'a':['b:x:y','other','b:x:y'],'n':[1.,2.,3.]})
        e=FrameEncoder().fit(d);f=FrameEncoder.from_spec(json.loads(json.dumps(e.to_spec())))
        self.assertEqual(len(set(e.keys)),len(e.keys))
        np.testing.assert_allclose(e.transform(d)[0],f.transform(d)[0])

    def test_rfe_cached_path_equals_independent_runs(self):
        d=self.data();e=FrameEncoder().fit(d.drop(columns='y'));z=e.transform(d)[0]
        path=rfe_path(z,d.y.to_numpy(),'identity',[1,2,3,4],Guard())
        for k in path:
            expected=RFE(LinearRegression(),n_features_to_select=k,step=1).fit(z,d.y).get_support()
            self.assertEqual(path[k],np.flatnonzero(expected).tolist())

    def test_sfs_cached_fold_preprocessing_matches_independent_pipeline(self):
        d=self.data(120);X=d.drop(columns='y');e=FrameEncoder().fit(X)
        cfg=self.config();path,trace=sfs_path(X,d.y.to_numpy(),e.keys,'identity',[1,2],cfg,Guard())
        reference=SequentialFeatureSelector(make_pipeline(StandardScaler(),LinearRegression()),n_features_to_select=2,
            cv=KFold(3,shuffle=True,random_state=cfg.seed+101),scoring='neg_mean_squared_error',n_jobs=1).fit(X,d.y)
        self.assertEqual(path[2],np.flatnonzero(reference.get_support()).tolist())
        self.assertEqual(trace['regression_fits'],(4+3)*3)

    def test_cv_preprocessor_fingerprints_are_training_only(self):
        d=self.data();d.loc[0,'a']=10000
        result=run_analysis(d,self.config())
        for info,(tr,va) in zip(result['folds'],folds_for(d,3,17)):
            spec=FrameEncoder().fit(d.drop(columns='y').iloc[tr]).to_spec()
            expected=hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()
            self.assertEqual(info['training_only_preprocessor_sha256'],expected)
            self.assertEqual(info['preprocessing_fit_rows'],len(tr))

    def test_exported_predictions_equal_independent_OLS(self):
        d=self.data();result=run_analysis(d,self.config());artifact=result['models']['ols']
        enc=FrameEncoder.from_spec(artifact['preprocessor']);z=enc.transform(d)[0]
        expected=LinearRegression().fit(z,d.y).predict(z)
        actual,_=predict_artifact(json.loads(json.dumps(artifact,allow_nan=False)),d)
        np.testing.assert_allclose(actual,expected,atol=1e-10)

    def test_zero_nonzero_lasso_is_intercept_only(self):
        cfg=self.config();cfg=dataclasses.replace(cfg,methods=('lasso_select',),alphas=(1e6,))
        d=self.data();r=run_analysis(d,cfg);model=next(iter(r['models'].values()))
        self.assertEqual(model['selected_keys'],[]);self.assertFalse(model['zero_coefficients_padded'])
        np.testing.assert_allclose(predict_artifact(model,d)[0],d.y.mean())

    def test_log_export_prediction_semantics(self):
        d=self.data();d.y=np.exp(d.y/4)
        r=run_analysis(d,self.config(target_transform='log'));m=r['models']['ols']
        z=FrameEncoder.from_spec(m['preprocessor']).transform(d)[0]
        expected=np.exp(LinearRegression().fit(z,np.log(d.y)).predict(z))
        np.testing.assert_allclose(predict_artifact(m,d)[0],expected,rtol=1e-10)
        self.assertIn('geometric',m['point_prediction_semantics'])

    def test_log_invalid_target_rejected(self):
        with self.assertRaises(InputError):run_analysis(self.data(),self.config(target_transform='log'))

    def test_missing_target_rejected_not_imputed(self):
        d=self.data();d.loc[0,'y']=np.nan
        with self.assertRaises(InputError):run_analysis(d,self.config())

    def test_inf_predictor_rejected(self):
        d=self.data();d.loc[0,'a']=np.inf
        with self.assertRaises(InputError):run_analysis(d,self.config())

    def test_repeated_input_vectors_kept_in_one_fold(self):
        d=self.data(30);d=pd.concat([d,d.assign(y=d.y+1)],ignore_index=True)
        r=run_analysis(d,self.config());a=r['cv_validation_fold_by_row']
        self.assertEqual(a[:30],a[30:]);self.assertIn('identical',r['cv_strategy'])

    def test_explicit_groups_excluded_from_predictors(self):
        d=self.data();d['person']=np.repeat(np.arange(30),3)
        r=run_analysis(d,self.config(group_column='person'))
        self.assertNotIn('person',r['input_fields'])
        a=np.asarray(r['cv_validation_fold_by_row'])
        self.assertTrue(all(len(set(a[d.person==g]))==1 for g in d.person.unique()))

    def test_rank_deficiency_reported_for_inference(self):
        d=self.data();d['duplicate']=d.a
        r=run_analysis(d,self.config());m=r['models']['ols']
        self.assertEqual(m['model']['inference_status'],'unavailable_rank_or_df')

    def test_deadline_returns_honest_partial_result(self):
        r=run_analysis(self.data(),self.config(budget_seconds=0))
        self.assertEqual(r['status'],'partial_timeout');self.assertEqual(r['models'],{})
        self.assertFalse(r['representative_model_available'])
        self.assertEqual(r['events'][-1]['status'],'partial_timeout')

    def test_cancel_mid_cv_does_not_publish_partial_scores_as_complete(self):
        event=threading.Event()
        def progress(msg):
            if msg['event']=='fold_completed':event.set()
        r=run_analysis(self.data(),self.config(),progress=progress,cancel=event.is_set)
        self.assertEqual(r['status'],'cancelled')
        self.assertTrue(all(x['status']!='completed' and 'cv' not in x for x in r['cv_results']))
        self.assertEqual(r['models'],{})

    def test_constant_target_has_no_fake_r2(self):
        d=self.data();d.y=7.
        r=run_analysis(d,self.config());self.assertIsNone(r['cv_results'][0]['cv']['r2'])
        self.assertEqual(r['cv_results'][0]['cv']['rmse'],0.)

    def test_encoded_budget_enforced(self):
        with self.assertRaises(InputError):run_analysis(self.data(),self.config(max_encoded_features=2))

    def test_reproducibility_same_data_config(self):
        d=self.data();a=run_analysis(d,self.config());b=run_analysis(d,self.config())
        self.assertEqual(a['cv_results'],b['cv_results']);self.assertEqual(a['models'],b['models'])

if __name__=='__main__':unittest.main()
