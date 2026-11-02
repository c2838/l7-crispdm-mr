import copy
import json
import unittest
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from l7_analysis.preprocessing import FrameEncoder
from l7_analysis.models import fit_linear,predict_artifact
from l7_analysis.config import InputError
from l7_analysis.inference import fit_inference,predict_with_intervals,design_for,coefficient_intervals,interval_summary
from l7_analysis.diagnostics import influence_arrays,deletion_sensitivity,diagnose

def fixture(log=False,n=80):
    rng=np.random.default_rng(114)
    frame=pd.DataFrame({'x':rng.normal(10,3,n),'z':rng.normal(2,1,n)})
    target=3+2*frame.x-frame.z+rng.normal(0,2,n)
    frame['y']=np.exp(target/10) if log else target
    enc=FrameEncoder().fit(frame[['x','z']]);matrix=enc.transform(frame)[0]
    artifact={'method':'ols','target':'y','target_transform':'log' if log else 'identity',
      'preprocessor':enc.to_spec(),'selected_keys':enc.keys,'selected_columns':enc.columns,
      'model':fit_linear(matrix,frame.y.to_numpy(),'log' if log else 'identity')}
    return frame,artifact

class InferenceTests(unittest.TestCase):
    def test_classical_intervals_equal_closed_form(self):
        frame,a=fixture();b=fit_inference(a,frame);X=design_for(a,frame.iloc[:6])[0]
        pred,notes=predict_with_intervals(a,b['spec'],frame.iloc[:6])
        xt=b['design'];y=frame.y.to_numpy();beta=np.linalg.lstsq(xt,y,rcond=None)[0]
        variance=np.sum((y-xt@beta)**2)/(len(y)-xt.shape[1]);cov=np.linalg.inv(xt.T@xt)*variance
        hm=stats.t.ppf(.975,len(y)-xt.shape[1])*np.sqrt(np.einsum('ij,jk,ik->i',X,cov,X))
        np.testing.assert_allclose(pred.location_ci_lower,X@beta-hm,atol=1e-10)
        hp=stats.t.ppf(.975,len(y)-xt.shape[1])*np.sqrt(variance+np.einsum('ij,jk,ik->i',X,cov,X))
        np.testing.assert_allclose(pred.observation_pi_upper,X@beta+hp,atol=1e-10)

    def test_matches_statsmodels_mean_PI_and_HC3(self):
        frame,a=fixture();b=fit_inference(a,frame);X=design_for(a,frame.iloc[:9])[0]
        got,_=predict_with_intervals(a,b['spec'],frame.iloc[:9])
        reference=b['fit'].get_prediction(X).summary_frame();robust=b['robust'].get_prediction(X).summary_frame()
        np.testing.assert_allclose(got.location_ci_upper,reference.mean_ci_upper)
        np.testing.assert_allclose(got.observation_pi_lower,reference.obs_ci_lower)
        np.testing.assert_allclose(got.location_ci_hc3_lower,robust.mean_ci_lower)

    def test_hc3_does_not_get_claimed_as_robust_observation_PI(self):
        frame,a=fixture();b=fit_inference(a,frame);one,_=predict_with_intervals(a,b['spec'],frame)
        spec=copy.deepcopy(b['spec']);spec['covariance_hc3']=(np.asarray(spec['covariance_hc3'])*9).tolist()
        two,_=predict_with_intervals(a,spec,frame)
        np.testing.assert_allclose(one.observation_pi_lower,two.observation_pi_lower)
        self.assertGreater((two.location_ci_hc3_upper-two.location_ci_hc3_lower).mean(),(one.location_ci_hc3_upper-one.location_ci_hc3_lower).mean())

    def test_coefficient_unscaling_matches_raw_design(self):
        frame,a=fixture();b=fit_inference(a,frame)
        rows=[r for r in coefficient_intervals(b) if r['basis']=='unscaled_encoded' and r['covariance']=='classical']
        direct=sm.OLS(frame.y.to_numpy(),sm.add_constant(frame[['x','z']].to_numpy())).fit()
        np.testing.assert_allclose([r['coefficient'] for r in rows],direct.params,atol=1e-10)
        np.testing.assert_allclose([[r['ci_lower'],r['ci_upper']] for r in rows],direct.conf_int(),atol=1e-10)

    def test_log_backtransform_and_location_label(self):
        frame,a=fixture(log=True);b=fit_inference(a,frame);got,_=predict_with_intervals(a,b['spec'],frame)
        np.testing.assert_allclose(got.location_ci_lower,np.exp(got.regression_location_ci_lower))
        np.testing.assert_allclose(got.observation_pi_upper,np.exp(got.regression_observation_pi_upper))
        self.assertIn('not arithmetic',b['spec']['location_kind'])

    def test_single_row_batch_and_JSON_roundtrip(self):
        frame,a=fixture();b=fit_inference(a,frame);spec=json.loads(json.dumps(b['spec']))
        batch,_=predict_with_intervals(a,spec,frame.iloc[:3])
        for i in range(3):
            single,_=predict_with_intervals(a,spec,frame.iloc[[i]])
            np.testing.assert_allclose(single.to_numpy()[0],batch.to_numpy()[i],atol=1e-10)

    def test_stale_interval_spec_rejected(self):
        frame,a=fixture();b=fit_inference(a,frame);changed=copy.deepcopy(a);changed['model']['intercept']+=1
        with self.assertRaises(InputError):predict_with_intervals(changed,b['spec'],frame)

    def test_rank_deficient_and_zero_noise_inference_unavailable(self):
        frame,a=fixture();frame['copy']=frame.x
        enc=FrameEncoder().fit(frame[['x','copy']]);a.update(preprocessor=enc.to_spec(),selected_keys=enc.keys,selected_columns=enc.columns,
          model=fit_linear(enc.transform(frame)[0],frame.y.to_numpy()))
        self.assertEqual(fit_inference(a,frame)['status'],'unavailable_rank_or_df')
        frame,a=fixture();frame.y=2*frame.x+1
        a['model']=fit_linear(FrameEncoder.from_spec(a['preprocessor']).transform(frame)[0],frame.y.to_numpy())
        self.assertEqual(fit_inference(a,frame)['status'],'unavailable_numerically_zero_residual_variance')

    def test_regularized_model_inference_rejected(self):
        frame,a=fixture();a['method']='ridge'
        with self.assertRaises(InputError):fit_inference(a,frame)

    def test_coverage_is_PI_only_and_uses_all_rows(self):
        frame,a=fixture();b=fit_inference(a,frame);got,_=predict_with_intervals(a,b['spec'],frame)
        y=frame.y.to_numpy();y[0]=1e6
        summary=interval_summary(y,got)
        expected=((y>=got.observation_pi_lower)&(y<=got.observation_pi_upper)).sum()
        self.assertEqual(summary['covered_count'],int(expected));self.assertEqual(summary['rows'],len(frame))
        self.assertIsNone(summary['location_ci_coverage_against_individual_y'])

    def test_influence_matches_statsmodels_without_leave_one_out_loop(self):
        frame,a=fixture();b=fit_inference(a,frame);got=influence_arrays(b);reference=b['fit'].get_influence()
        np.testing.assert_allclose(got['leverage'],reference.hat_matrix_diag,atol=1e-10)
        np.testing.assert_allclose(got['cooks_distance'],reference.cooks_distance[0],atol=1e-10)

    def test_deletion_sensitivity_matches_one_actual_refit(self):
        frame,a=fixture();b=fit_inference(a,frame);got=deletion_sensitivity(b,4)
        X=np.delete(b['design'],4,axis=0);y=np.delete(b['response'],4)
        expected=np.linalg.lstsq(X,y,rcond=None)[0]
        np.testing.assert_allclose(got['coefficients_after_one_row_deletion'],expected,atol=1e-10)
        self.assertFalse(got['production_model_changed']);self.assertEqual(got['test_rows_deleted'],0)

    def test_diagnostics_scope_and_source_row_mapping(self):
        frame,a=fixture();b=fit_inference(a,frame);d,p=diagnose(b,np.arange(len(frame))+1000,max_points=10)
        self.assertEqual(d['training_rows'],len(frame));self.assertEqual(len(p['fitted']),10)
        self.assertEqual(d['independence']['status'],'not_established')
        self.assertGreaterEqual(d['influence']['top_rows'][0]['source_row_index_0_based'],1000)

if __name__=='__main__':unittest.main()
