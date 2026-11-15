"""Self-contained interactive dashboard (one HTML file, Plotly embedded, works offline): docs/dashboard.html

Tabs: (1) CAC / POAS / LTV by channel and country, (2) attribution with intervals, (3) saturation curves,
(4) test planner (A/B sample size and geo-test MDE, computed live in the browser).
    python src/build_dashboard.py
"""
import json
from pathlib import Path

import pandas as pd
from plotly.offline import get_plotlyjs

ROOT = Path(__file__).resolve().parents[1]
OUTD = ROOT / "data" / "output"
DOCS = ROOT / "docs"
CH_COLORS = {"Google Search": "#2A78D6", "Google Shopping": "#EB6834", "Microsoft Ads": "#1BAF7A",
             "Meta": "#EDA100", "Marketplaces": "#E87BA4"}


def records(name, cols=None):
    d = pd.read_csv(OUTD / f"{name}.csv")
    if cols:
        d = d[cols]
    return json.loads(d.round(4).to_json(orient="records"))


def data():
    h = json.loads((OUTD / "headline.json").read_text(encoding="utf-8"))
    cc = pd.read_csv(OUTD / "channel_country_economics.csv")
    lt = pd.read_csv(OUTD / "cohort_ltv.csv")
    ltv = lt[(lt.months == 12) & lt.segment.isna() & lt.acquisition_channel.notna()].set_index("acquisition_channel").gp_ltv_eur
    cv = pd.read_csv(OUTD / "customer_value.csv")
    ltv_cc = cv.groupby(["acquisition_channel", "country"]).gp_12m_eur.mean()
    cc["ltv12"] = [ltv_cc.get((r.channel, r.country)) for r in cc.itertuples()]
    return {
        "colors": CH_COLORS,
        "cc": json.loads(cc.round(3).to_json(orient="records")),
        "ltv": ltv.round(1).to_dict(),
        "attr": records("attribution_ci"),
        "curves": records("response_curves"),
        "marg": records("incremental_poas"),
        "realloc": records("reallocation"),
        "geo": records("geo_mde"),
        "ab": {"p0": h["ab_p0"], "sessions": h["ab_sessions_per_day"]},
        "geo_plan": records("geo_test_plan"),
    }


HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tameson paid acquisition dashboard</title>
<style>
:root { color-scheme: light; --bg:#F4F4F2; --card:#FCFCFB; --line:#E1E0D9; --ink:#0B0B0B; --muted:#52514E; --accent:#2A78D6; --pub:#E3EEFB; --pubt:#1C5CAB; --sim:#FBE9E0; --simt:#9A3B12; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { color-scheme: dark; --bg:#141413; --card:#1A1A19; --line:#33322F; --ink:#F0EFEC; --muted:#C3C2B7; --accent:#3987E5; --pub:#1C2E45; --pubt:#9CC3F2; --sim:#40261A; --simt:#F2B89C; } }
:root[data-theme="dark"] { color-scheme: dark; --bg:#141413; --card:#1A1A19; --line:#33322F; --ink:#F0EFEC; --muted:#C3C2B7; --accent:#3987E5; --pub:#1C2E45; --pubt:#9CC3F2; --sim:#40261A; --simt:#F2B89C; }
* { box-sizing: border-box; }
body { margin:0; font-family:'Segoe UI', Arial, sans-serif; background:var(--bg); color:var(--ink); }
.wrap { max-width:1280px; margin:0 auto; padding:20px 16px 40px; }
h1 { font-size:24px; margin:0 0 4px; } .sub { color:var(--muted); margin:0 0 14px; font-size:14px; }
nav { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:12px; }
nav button { border:1px solid var(--line); background:var(--card); color:var(--ink); padding:7px 12px; border-radius:6px; cursor:pointer; font:inherit; font-size:14px; }
nav button.on { border-color:var(--accent); color:var(--accent); font-weight:600; }
.tab { display:none; } .tab.on { display:block; }
.grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(340px, 1fr)); gap:12px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 14px; min-width:0; }
.card h2 { font-size:15px; margin:0 0 6px; } .card p { font-size:13px; color:var(--muted); margin:4px 0; }
.tag { font-size:11px; font-weight:700; letter-spacing:.06em; padding:3px 7px; border-radius:4px; margin-left:6px; vertical-align:middle; }
.pub { background:var(--pub); color:var(--pubt); } .sim { background:var(--sim); color:var(--simt); }
.ctrl { display:flex; gap:12px; flex-wrap:wrap; align-items:center; margin:6px 0 10px; font-size:13px; color:var(--muted); }
select, input { font:inherit; font-size:13px; padding:4px 6px; border:1px solid var(--line); border-radius:5px; background:var(--card); color:var(--ink); }
input[type=number] { width:90px; }
.big { font-size:30px; font-weight:700; color:var(--ink); margin:4px 0; }
table { border-collapse:collapse; width:100%; font-size:13px; } th, td { text-align:left; padding:4px 6px; border-bottom:1px solid var(--line); }
th { color:var(--muted); font-weight:600; }
footer { margin-top:18px; font-size:12px; color:var(--muted); }
.plot { width:100%; height:340px; }
</style></head><body><div class="wrap">
<h1>Tameson · paid acquisition on profit</h1>
<p class="sub">Interactive companion to the case study. Simulated business data (not Tameson's numbers) and real public data, tagged on each view.</p>
<nav id="nav"><button data-t="t1" class="on">CAC · POAS · LTV</button><button data-t="t2">Attribution</button><button data-t="t3">Saturation</button><button data-t="t4">Test planner</button></nav>

<section id="t1" class="tab on">
 <div class="ctrl">Country <select id="country"><option value="ALL">All countries</option></select> <span class="tag sim">SIMULATED</span></div>
 <div class="grid">
  <div class="card"><h2>POAS vs ROAS by channel (last click)</h2><div id="c_poas" class="plot"></div></div>
  <div class="card"><h2>CAC vs 12-month gross-profit LTV per new customer</h2><div id="c_cac" class="plot"></div></div>
 </div>
 <div class="card" style="margin-top:12px"><h2>Table</h2><div id="c_table"></div></div>
</section>

<section id="t2" class="tab">
 <div class="grid">
  <div class="card"><h2>Share of conversions credited, 90% bootstrap interval <span class="tag pub">PUBLIC DATA</span></h2><div id="a_ci" class="plot" style="height:380px"></div>
   <p>Real journeys from Google's public GA4 sample (Google Merchandise Store). Markov = removal effect; intervals from 500 resamples of users.</p></div>
  <div class="card"><h2>Table</h2><div id="a_table"></div></div>
 </div>
</section>

<section id="t3" class="tab">
 <div class="ctrl">Channel <select id="channel"></select> <span class="tag sim">SIMULATED</span></div>
 <div class="grid">
  <div class="card"><h2>Weekly gross profit vs weekly spend</h2><div id="s_curve" class="plot"></div><p>Band = P10–P90 over 50 bootstrap refits; dotted = true curve of the simulation; vertical = current spend.</p></div>
  <div class="card"><h2>Gross profit from the next euro</h2><div id="s_marg" class="plot"></div><p>Below 1, the next euro loses money on first orders.</p></div>
 </div>
 <div class="card" style="margin-top:12px"><h2>Reallocation, same total budget (€k a week)</h2><div id="s_table"></div></div>
</section>

<section id="t4" class="tab">
 <div class="grid">
  <div class="card"><h2>A/B test size</h2>
   <div class="ctrl">Baseline conversion % <input id="p0" type="number" step="0.01"> Sessions / day <input id="traffic" type="number" step="100"></div>
   <div class="ctrl">Smallest lift worth detecting % <input id="mde" type="number" value="10" step="1"> α <select id="alpha"><option>0.05</option><option>0.10</option><option>0.01</option></select>
    Power <select id="power"><option>0.8</option><option>0.9</option><option>0.7</option></select></div>
   <div class="big" id="ab_out"></div><p id="ab_note"></p>
   <div id="ab_plot" class="plot" style="height:260px"></div>
   <p>Defaults: real baseline of the public GA4 sample <span class="tag pub">PUBLIC DATA</span>. Two-sided z-test for two proportions, 50/50 split.</p></div>
  <div class="card"><h2>Geo test: minimum detectable effect by duration</h2>
   <div class="ctrl">Pre-period weeks <input id="npre" type="number" value="26" step="1"></div>
   <div id="geo_plot" class="plot"></div>
   <p>Weekly noise of 'country / other stores' from Google Trends (5 years) <span class="tag pub">PUBLIC DATA</span>. A proxy: real sales noise must be measured on Tameson's own data.</p></div>
 </div>
 <div class="card" style="margin-top:12px"><h2>Geo holdout designs compared before launch <span class="tag sim">SIMULATED</span></h2><div id="geo_table"></div></div>
</section>
<footer>Independent case study based on public data · not affiliated with or endorsed by Tameson. Sources: data/SOURCES.md.</footer>
</div>
<script>__PLOTLY__</script>
<script>
const D = __DATA__;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const CH = Object.keys(D.colors);
const layout = (extra) => Object.assign({margin:{l:110,r:20,t:10,b:45}, paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
  font:{family:'Segoe UI, Arial', size:12, color:css('--muted')}, xaxis:{gridcolor:css('--line'), zeroline:false},
  yaxis:{gridcolor:css('--line'), zeroline:false}, legend:{orientation:'h', y:1.12}, hoverlabel:{font:{family:'Segoe UI'}}}, extra||{});
const cfg = {displayModeBar:false, responsive:true};
const fmt = (v, d=2) => v==null ? '–' : Number(v).toLocaleString('en', {maximumFractionDigits:d, minimumFractionDigits:d});
const table = (el, cols, rows) => { document.getElementById(el).innerHTML = '<table><tr>' + cols.map(c=>'<th>'+c[0]+'</th>').join('') + '</tr>' +
  rows.map(r=>'<tr>'+cols.map(c=>'<td>'+c[1](r)+'</td>').join('')+'</tr>').join('') + '</table>'; };

document.querySelectorAll('#nav button').forEach(b => b.onclick = () => {
  document.querySelectorAll('#nav button').forEach(x=>x.classList.toggle('on', x===b));
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on', t.id===b.dataset.t));
  document.querySelectorAll('#'+b.dataset.t+' .js-plotly-plot').forEach(el => Plotly.Plots.resize(el));   // drawn while hidden
});

// ---- tab 1
const countries = [...new Set(D.cc.map(r=>r.country))];
countries.forEach(c => document.getElementById('country').insertAdjacentHTML('beforeend', `<option>${c}</option>`));
function econ() {
  const c = document.getElementById('country').value;
  const rows = CH.map(ch => {
    const r = D.cc.filter(x => x.channel===ch && (c==='ALL' || x.country===c));
    const s = k => r.reduce((a,x)=>a+(x[k]||0),0);
    const ltv = c==='ALL' ? D.ltv[ch] : (r[0]||{}).ltv12;
    return {ch, spend:s('spend_eur'), roas:s('revenue_eur')/s('spend_eur'), poas:s('gross_profit_eur')/s('spend_eur'), cac:s('spend_eur')/s('new_customers'), ltv};
  });
  Plotly.react('c_poas', [
    {type:'bar', orientation:'h', name:'ROAS', y:rows.map(r=>r.ch), x:rows.map(r=>r.roas), marker:{color:'#A3A19A'}, hovertemplate:'%{y}: ROAS %{x:.2f}<extra></extra>'},
    {type:'bar', orientation:'h', name:'POAS', y:rows.map(r=>r.ch), x:rows.map(r=>r.poas), marker:{color:rows.map(r=>D.colors[r.ch])}, hovertemplate:'%{y}: POAS %{x:.2f}<extra></extra>'}],
    layout({barmode:'group', yaxis:{autorange:'reversed', gridcolor:css('--line')}, shapes:[{type:'line', x0:1, x1:1, yref:'paper', y0:0, y1:1, line:{color:'#D03B3B', dash:'dash', width:1}}]}), cfg);
  Plotly.react('c_cac', [
    {type:'bar', orientation:'h', name:'CAC (€)', y:rows.map(r=>r.ch), x:rows.map(r=>r.cac), marker:{color:'#A3A19A'}, hovertemplate:'%{y}: CAC €%{x:,.0f}<extra></extra>'},
    {type:'bar', orientation:'h', name:'12-month GP LTV (€)', y:rows.map(r=>r.ch), x:rows.map(r=>r.ltv), marker:{color:rows.map(r=>D.colors[r.ch])}, hovertemplate:'%{y}: LTV €%{x:,.0f}<extra></extra>'}],
    layout({barmode:'group', yaxis:{autorange:'reversed', gridcolor:css('--line')}}), cfg);
  table('c_table', [['Channel', r=>r.ch], ['Spend', r=>'€'+fmt(r.spend,0)], ['ROAS', r=>fmt(r.roas)], ['POAS', r=>fmt(r.poas)],
    ['CAC', r=>'€'+fmt(r.cac,0)], ['12-m LTV', r=>'€'+fmt(r.ltv,0)], ['LTV / CAC', r=>fmt(r.ltv/r.cac)]], rows);
}
document.getElementById('country').onchange = econ; econ();

// ---- tab 2
const A = D.attr.slice().sort((a,b)=>a.markov-b.markov);
Plotly.newPlot('a_ci', [
  {type:'scatter', mode:'markers', name:'Last click', y:A.map(r=>r.channel), x:A.map(r=>r.last_click), marker:{color:'#A3A19A', size:10},
   error_x:{type:'data', symmetric:false, array:A.map(r=>r.lc_hi-r.last_click), arrayminus:A.map(r=>r.last_click-r.lc_lo), color:'#A3A19A'}, hovertemplate:'%{y}: %{x:.1%}<extra>Last click</extra>'},
  {type:'scatter', mode:'markers', name:'Markov', y:A.map(r=>r.channel), x:A.map(r=>r.markov), marker:{color:css('--accent'), size:10},
   error_x:{type:'data', symmetric:false, array:A.map(r=>r.mk_hi-r.markov), arrayminus:A.map(r=>r.markov-r.mk_lo), color:css('--accent')}, hovertemplate:'%{y}: %{x:.1%}<extra>Markov</extra>'}],
  layout({margin:{l:150,r:20,t:10,b:45}, xaxis:{tickformat:'.0%', gridcolor:css('--line')}}), cfg);
table('a_table', [['Channel', r=>r.channel], ['Last-click conv.', r=>fmt(r.conversions_last_click,0)], ['Last click', r=>fmt(r.last_click*100,1)+'%'],
  ['Markov (90%)', r=>fmt(r.markov*100,1)+'% ('+fmt(r.mk_lo*100,1)+'–'+fmt(r.mk_hi*100,1)+')'], ['Markov, Direct not a channel', r=>fmt(r.markov_no_direct*100,1)+'%'],
  ['Gap clear?', r=>r.diff_is_clear ? 'yes' : 'no']], D.attr.slice().sort((a,b)=>b.markov-a.markov));

// ---- tab 3
CH.forEach(c => document.getElementById('channel').insertAdjacentHTML('beforeend', `<option>${c}</option>`));
function sat() {
  const ch = document.getElementById('channel').value, d = D.curves.filter(r=>r.channel===ch), col = D.colors[ch];
  const cur = d[0].current_k, x = d.map(r=>r.spend_k);
  Plotly.react('s_curve', [
    {x, y:d.map(r=>r.gp_p90), mode:'lines', line:{width:0}, showlegend:false, hoverinfo:'skip'},
    {x, y:d.map(r=>r.gp_p10), mode:'lines', line:{width:0}, fill:'tonexty', fillcolor:col+'33', name:'P10–P90', hoverinfo:'skip'},
    {x, y:d.map(r=>r.gp_fit), mode:'lines', line:{color:col, width:2.5}, name:'model', hovertemplate:'spend €%{x:.1f}k → GP €%{y:.1f}k<extra>model</extra>'},
    {x, y:d.map(r=>r.gp_true), mode:'lines', line:{color:css('--ink'), width:1.3, dash:'dot'}, name:'truth', hovertemplate:'€%{y:.1f}k<extra>truth</extra>'}],
    layout({margin:{l:55,r:20,t:10,b:45}, xaxis:{title:'weekly spend, €k', gridcolor:css('--line')}, yaxis:{title:'weekly gross profit, €k', gridcolor:css('--line')},
      shapes:[{type:'line', x0:cur, x1:cur, yref:'paper', y0:0, y1:1, line:{color:'#A3A19A', width:1}}]}), cfg);
  Plotly.react('s_marg', [
    {x, y:d.map(r=>r.marginal_p90), mode:'lines', line:{width:0}, showlegend:false, hoverinfo:'skip'},
    {x, y:d.map(r=>r.marginal_p10), mode:'lines', line:{width:0}, fill:'tonexty', fillcolor:col+'33', name:'P10–P90', hoverinfo:'skip'},
    {x, y:d.map(r=>r.marginal_fit), mode:'lines', line:{color:col, width:2.5}, name:'marginal POAS', hovertemplate:'spend €%{x:.1f}k → %{y:.2f}<extra></extra>'}],
    layout({margin:{l:55,r:20,t:10,b:45}, xaxis:{title:'weekly spend, €k', gridcolor:css('--line')}, yaxis:{title:'€ gross profit per extra €', gridcolor:css('--line')},
      shapes:[{type:'line', xref:'paper', x0:0, x1:1, y0:1, y1:1, line:{color:'#D03B3B', dash:'dash', width:1}},
              {type:'line', x0:cur, x1:cur, yref:'paper', y0:0, y1:1, line:{color:'#A3A19A', width:1}}]}), cfg);
}
document.getElementById('channel').onchange = sat; sat();
table('s_table', [['Channel', r=>r.channel], ['Today', r=>fmt(r.current_k,1)], ['Recommended', r=>fmt(r.recommended_k,1)],
  ['P10–P90', r=>fmt(r.rec_p10,1)+'–'+fmt(r.rec_p90,1)], ['Change', r=>(r.change_k>0?'+':'')+fmt(r.change_k,1)]], D.realloc);

// ---- tab 4: planner (inverse normal CDF, Acklam's approximation)
function qnorm(p) { const a=[-39.6968302866538,220.946098424521,-275.928510446969,138.357751867269,-30.6647980661472,2.50662827745924],
  b=[-54.4760987982241,161.585836858041,-155.698979859887,66.8013118877197,-13.2806815528857], c=[-0.00778489400243029,-0.322396458041136,-2.40075827716184,-2.54973253934373,4.37466414146497,2.93816398269878],
  d=[0.00778469570904146,0.32246712907004,2.445134137143,3.75440866190742], pl=0.02425; let q, r;
  if (p < pl) { q=Math.sqrt(-2*Math.log(p)); return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1); }
  if (p > 1-pl) { q=Math.sqrt(-2*Math.log(1-p)); return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1); }
  q=p-0.5; r=q*q; return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1); }
function nArm(p0, rel, alpha, power) { const p1=p0*(1+rel), za=qnorm(1-alpha/2), zb=qnorm(power), pb=(p0+p1)/2;
  return Math.ceil(Math.pow(za*Math.sqrt(2*pb*(1-pb)) + zb*Math.sqrt(p0*(1-p0)+p1*(1-p1)), 2) / Math.pow(p1-p0, 2)); }
document.getElementById('p0').value = (D.ab.p0*100).toFixed(2);
document.getElementById('traffic').value = Math.round(D.ab.sessions/100)*100;
function ab() {
  const p0 = +document.getElementById('p0').value/100, tr = +document.getElementById('traffic').value, mde = +document.getElementById('mde').value/100,
        al = +document.getElementById('alpha').value, pw = +document.getElementById('power').value;
  if (!(p0>0 && p0<1 && tr>0 && mde>0)) return;
  const n = nArm(p0, mde, al, pw), days = Math.ceil(2*n/tr);
  document.getElementById('ab_out').textContent = n.toLocaleString('en') + ' users per arm · ' + days + ' days';
  document.getElementById('ab_note').textContent = days > 56 ? 'Longer than 8 weeks: test a bigger change, a higher-traffic page, or a metric closer to the change (add-to-cart).' : 'Run the full duration; do not stop at the first significant day.';
  const lifts = [0.03,0.05,0.075,0.1,0.15,0.2,0.3];
  Plotly.react('ab_plot', [{type:'bar', x:lifts.map(l=>(l*100)+'%'), y:lifts.map(l=>Math.ceil(2*nArm(p0,l,al,pw)/tr)), marker:{color:css('--accent')}, hovertemplate:'lift %{x}: %{y} days<extra></extra>'}],
    layout({margin:{l:55,r:20,t:10,b:40}, yaxis:{title:'days needed', gridcolor:css('--line')}, xaxis:{title:'smallest lift to detect'}}), cfg);
}
['p0','traffic','mde','alpha','power'].forEach(id => document.getElementById(id).oninput = ab); ab();
function geo() {
  const npre = Math.max(4, +document.getElementById('npre').value || 26), z = qnorm(0.975) + qnorm(0.8);
  const byC = {}; D.geo.forEach(r => byC[r.country] = r);
  const weeks = [2,4,6,8,10,12,16,20];
  const traces = Object.keys(byC).map((c,i) => { const r = byC[c], infl = Math.sqrt((1+Math.max(r.ar1,0))/(1-Math.max(r.ar1,0)));
    return {x:weeks, y:weeks.map(w => z*r.weekly_noise_sd*Math.sqrt(1/npre+1/w)*infl), mode:'lines+markers', name:c,
            line:{width:2}, marker:{size:8}, hovertemplate:c+': %{x} weeks → MDE %{y:.1%}<extra></extra>'}; });
  Plotly.react('geo_plot', traces, layout({margin:{l:55,r:20,t:10,b:45}, colorway:['#2A78D6','#EB6834','#1BAF7A','#EDA100','#E87BA4','#008300'],
    yaxis:{tickformat:'.0%', title:'minimum detectable lift', gridcolor:css('--line')}, xaxis:{title:'test weeks', gridcolor:css('--line')},
    shapes:[{type:'line', xref:'paper', x0:0, x1:1, y0:0.1, y1:0.1, line:{color:'#D03B3B', dash:'dash', width:1}}]}), cfg);
}
document.getElementById('npre').oninput = geo; geo();
table('geo_table', [['Channel', r=>r.channel], ['Test countries', r=>r.test_countries], ['Pre / test weeks', r=>r.pre_weeks+' / '+r.test_weeks],
  ['Incrementality assumed', r=>fmt(r.incrementality_assumed*100,0)+'%'], ['Expected lost GP', r=>'€'+fmt(r.expected_effect,0)], ['MDE', r=>'€'+fmt(r.mde,0)],
  ['Power', r=>fmt(r.power*100,0)+'%']], D.geo_plan);
</script></body></html>"""


def main():
    html = HTML.replace("__PLOTLY__", get_plotlyjs()).replace("__DATA__", json.dumps(data()))
    out = DOCS / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print("written", out, f"{out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
