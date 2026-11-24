import sys, json, math
sys.path.insert(0, '/home/claude/trading-bot')
from bot import backtest as bt, config, data, strategies as st
cfg = config.load(); s = data.build_series()
crisis = json.load(open('/home/claude/trading-bot/state/crisis.json'))['crises']

class FastReentry(st.Core):
    """Held assets are judged on the usual 3/6/12-month average; assets NOT held last month may come back on a
    faster 1/3/6-month average. Exits stay slow, entries get quicker."""
    def __init__(self, fast=(1, 3, 6), **kw):
        super().__init__(**kw); self.fast = fast; self.memo = {}; self.name = 'FAST-REENTRY'
    def _prev_held(self, s, me, i):
        j = me.back(i, 1)
        if j is None: return set()
        t = self._t(s, me, j)
        return {a for a, w in (t or {}).items() if w > 0.005 and a != 'CASH'}
    def scores(self, s, me, i):
        base = super().scores(s, me, i)
        if base is None: return None
        held = self._prev_held(s, me, i)
        out = dict(base)
        for a in self.risky:
            if a in held or a not in base: continue
            rs = [st.total_return(s, a, i, me.back(i, m)) for m in self.fast]
            if any(r is None for r in rs): continue
            out[a] = max(base[a], sum(rs) / len(rs))
        return out
    def _t(self, s, me, i):
        if i not in self.memo: self.memo[i] = super().target(s, me, i)
        return self.memo[i]
    def target(self, s, me, i):
        if i in self.memo: return self.memo[i]
        t = st.Core.target(self, s, me, i); self.memo[i] = t; return t

def stats(r):
    ds, eq = r.dates, r.equity; yrs = len(ds) / 252
    cagr = (eq[-1] / eq[0]) ** (1 / yrs) - 1
    pk = eq[0]; mdd = 0
    for v in eq: pk = max(pk, v); mdd = min(mdd, v / pk - 1)
    out = {'cagr': cagr, 'mdd': mdd, 'turnover': r.turnover() if callable(r.turnover) else r.turnover, 'crisis': {}}
    for c in crisis:
        if ds[0] > c['start'] or ds[-1] < c['end']: continue
        a = next((k for k, d in enumerate(ds) if d >= c['start']), None); b = max(k for k, d in enumerate(ds) if d <= c['end'])
        v0 = eq[a]; rec = next((k for k in range(b, len(eq)) if eq[k] >= v0), None)
        out['crisis'][c['name']] = (eq[b] / v0 - 1, (rec - a) / 21 if rec else None, eq[min(len(eq) - 1, b + 252)] / v0 - 1)
    return out
kw = dict(top_k=3, vol_cap=cfg['vol_cap'], lookbacks=(3, 6, 12), max_weight=cfg['max_single_asset'])
runs = {'Live rules': st.Core(**kw), 'Fast re-entry (1/3/6 for assets not held)': FastReentry((1, 3, 6), **kw), 'Fast re-entry (3/6 for assets not held)': FastReentry((3, 6), **kw)}
res = {}
for n, strat in runs.items():
    r = bt.run(s, strat, start='1986-06-01', cost_bps=cfg['cost_bps'], band=cfg['no_trade_band'], capital=10000.0)
    res[n] = stats(r)
    # out-of-sample style split
    for a, b in (('1986-06-01', '2006-12-31'), ('2007-01-01', None)):
        rr = bt.run(s, strat.__class__(**({'fast': strat.fast} if hasattr(strat, 'fast') else {}), **kw) if hasattr(strat, 'fast') else st.Core(**kw), start=a, end=b, cost_bps=cfg['cost_bps'], band=cfg['no_trade_band'], capital=10000.0)
        res[n][f'split {a[:4]}'] = stats(rr)
json.dump(res, open('/tmp/reentry.json', 'w'), default=float, indent=1)
for n, m in res.items():
    print(n, f"cagr {m['cagr']*100:.2f} mdd {m['mdd']*100:.1f} turnover {m['turnover']:.0f}", f"| 1986-2006 {m['split 1986']['cagr']*100:.2f}/{m['split 1986']['mdd']*100:.1f} | 2007- {m['split 2007']['cagr']*100:.2f}/{m['split 2007']['mdd']*100:.1f}")
    print('   ', {k[:22]: (round(v[0]*100,1), v[1] and round(v[1]), round(v[2]*100,1)) for k, v in m['crisis'].items()})
