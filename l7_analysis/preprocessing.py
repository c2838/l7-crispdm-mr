"""Fold-fitted median/mode imputation, drop-first encoding and full scaling.

The JSON specification is sufficient for inference; it contains no source rows.
Semantic encoded keys remain stable even when a fold has fewer categories.
"""
import json
import numpy as np
import pandas as pd
from .config import InputError

def key_for(field,category=None):
    return ('n:' if category is None else 'c:')+json.dumps(field if category is None else [field,category],ensure_ascii=False,separators=(',',':'))

class FrameEncoder:
    def __init__(self,categorical=()):self.categorical=set(categorical)

    @staticmethod
    def strings(series):
        return np.array([None if pd.isna(x) else str(x) for x in series],dtype=object)

    def fit(self,frame):
        self.fields=[];self.all_columns=[];blocks=[];self.fit_rows=len(frame)
        for name in frame:
            series=frame[name]
            if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series) and name not in self.categorical:
                values=pd.to_numeric(series,errors='raise').to_numpy(dtype=float)
                if np.isinf(values).any():raise InputError(f'Infinite numeric input: {name}')
                observed=values[~np.isnan(values)];fill=float(np.median(observed)) if len(observed) else 0.
                filled=np.where(np.isnan(values),fill,values)
                self.fields.append({'field':name,'kind':'numeric','fill':fill,'all_missing_training':not len(observed)})
                self.all_columns.append({'key':key_for(name),'field':name,'category':None,'label':name})
                blocks.append(filled)
            else:
                values=self.strings(series);present=[v for v in values if v is not None]
                if present:
                    counts=pd.Series(present).value_counts();largest=counts.max()
                    fill=sorted(counts[counts==largest].index)[0]
                else:fill='__ALL_MISSING__'
                filled=np.array([fill if v is None else v for v in values],dtype=object)
                categories=sorted(set(filled))
                self.fields.append({'field':name,'kind':'categorical','fill':fill,'categories':categories,
                                    'reference':categories[0],'all_missing_training':not len(present)})
                for category in categories[1:]:
                    self.all_columns.append({'key':key_for(name,category),'field':name,'category':category,'label':f'{name} = {category}'})
                    blocks.append((filled==category).astype(float))
        matrix=np.column_stack(blocks) if blocks else np.empty((len(frame),0))
        mean=matrix.mean(axis=0);scale=matrix.std(axis=0)
        if not np.isfinite(mean).all() or not np.isfinite(scale).all():raise InputError('Numeric scale overflow.')
        self.keep=np.flatnonzero(scale>0).tolist()
        self.columns=[self.all_columns[i] for i in self.keep]
        self.center=mean[self.keep];self.scale=scale[self.keep]
        self.dropped_constant=[x for i,x in enumerate(self.all_columns) if i not in self.keep]
        self.keys=[x['key'] for x in self.columns]
        return self

    def transform(self,frame,keys=None):
        data={};unknown={};missing={}
        for field in self.fields:
            name=field['field']
            if name not in frame:raise InputError(f'Required input missing: {name}')
            if field['kind']=='numeric':
                try:values=pd.to_numeric(frame[name],errors='raise').to_numpy(dtype=float)
                except (ValueError,TypeError) as e:raise InputError(f'Non-numeric value in {name}') from e
                if np.isinf(values).any():raise InputError(f'Infinite numeric input: {name}')
                missing[name]=int(np.isnan(values).sum())
                data[key_for(name)]=np.where(np.isnan(values),field['fill'],values)
            else:
                values=self.strings(frame[name]);missing[name]=sum(v is None for v in values)
                values=np.array([field['fill'] if v is None else v for v in values],dtype=object)
                unknown[name]=sum(v not in field['categories'] for v in values)
                for category in field['categories'][1:]:data[key_for(name,category)]=(values==category).astype(float)
        desired=self.keys if keys is None else list(keys)
        lookup={k:i for i,k in enumerate(self.keys)};result=[]
        for key in desired:
            if key in lookup:
                i=lookup[key];result.append((data[key]-self.center[i])/self.scale[i])
            else:
                # A category never observed in this fold cannot learn an effect.
                result.append(np.zeros(len(frame)))
        matrix=np.column_stack(result) if result else np.empty((len(frame),0))
        if not np.isfinite(matrix).all():raise InputError('Non-finite transformed inputs.')
        return matrix,{'unknown_categories':{k:int(v) for k,v in unknown.items() if v},
                       'imputed_values':{k:int(v) for k,v in missing.items() if v}}

    def fit_transform(self,frame):self.fit(frame);return self.transform(frame)[0]

    def to_spec(self):
        return {'fields':self.fields,'all_columns':self.all_columns,'keep':self.keep,'columns':self.columns,
                'center':self.center.tolist(),'scale':self.scale.tolist(),'fit_rows':self.fit_rows,
                'dropped_constant':self.dropped_constant,'categorical_overrides':sorted(self.categorical),
                'unknown_policy':'all-zero dummy block, equivalent to training reference; count reported',
                'scale_scope':'all active encoded columns, including numeric and binary dummies'}

    @classmethod
    def from_spec(cls,spec):
        obj=cls(spec.get('categorical_overrides',()))
        for name in ['fields','all_columns','keep','columns','fit_rows','dropped_constant']:setattr(obj,name,spec[name])
        obj.center=np.asarray(spec['center']);obj.scale=np.asarray(spec['scale']);obj.keys=[c['key'] for c in obj.columns]
        if (obj.scale<=0).any():raise InputError('Invalid exported preprocessing scale.')
        return obj
