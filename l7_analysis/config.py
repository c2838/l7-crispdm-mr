from dataclasses import dataclass
import time

METHODS = ('dummy','ols','kbest','rfe','sfs','lasso_select','elasticnet_select','ridge','lasso_reg')
OLS_METHODS = ('ols','kbest','rfe','sfs','lasso_select','elasticnet_select')

@dataclass(frozen=True)
class AnalysisConfig:
    target: str
    dataset_id: str = 'custom'
    target_transform: str = 'identity'
    exclude: tuple = ()
    categorical: tuple = ()
    group_column: str | None = None
    outer_folds: int = 5
    inner_folds: int = 3
    seed: int = 17
    methods: tuple = METHODS
    k_values: tuple | None = None
    alphas: tuple = (.0001,.001,.01,.1,1.,10.)
    l1_ratios: tuple = (.2,.5,.8)
    ridge_alphas: tuple = (.0001,.001,.01,.1,1.,10.,100.,1000.,10000.)
    max_encoded_features: int = 64
    budget_seconds: float | None = None

    def validate(self):
        if not self.target or self.target_transform not in ('identity','log'):
            raise InputError('Target and transform must be explicitly valid.')
        if self.outer_folds<2 or self.inner_folds<2:raise InputError('At least two CV folds required.')
        if not set(self.methods)<=set(METHODS):raise InputError('Unknown selection method.')
        if any(a<=0 for a in self.alphas+self.ridge_alphas):raise InputError('Alphas must be positive.')
        if any(not 0<r<=1 for r in self.l1_ratios):raise InputError('l1_ratio must be in (0,1].')
        if self.k_values is not None and any(k<1 for k in self.k_values):raise InputError('k must be positive.')
        if self.max_encoded_features<1:raise InputError('Encoded feature budget must be positive.')

class InputError(ValueError):pass
class BudgetExceeded(RuntimeError):pass
class Cancelled(RuntimeError):pass

class Guard:
    def __init__(self, seconds=None, cancel=None):
        self.started=time.perf_counter();self.seconds=seconds;self.cancel=cancel
    def check(self):
        if self.cancel is not None and self.cancel():raise Cancelled('Cancellation acknowledged at a computation checkpoint.')
        if self.seconds is not None and time.perf_counter()-self.started>=self.seconds:
            raise BudgetExceeded('Computation deadline reached; completed results retained.')
