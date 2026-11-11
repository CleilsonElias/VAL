"""Fill the revised manuscript from recorded outputs and draw its exact figure."""
from pathlib import Path
import json
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/"results/revision_study.json").read_text())
summary={(r["scenario"],r["routing_error"],r["policy"]):r for r in data["summaries"]}
codes={"uniform_legacy":"U-L Uniform legacy", "selective_legacy":"V-L Selective legacy",
       "uniform_consistent":"U-R Uniform revised", "selective_consistent":"V-R Selective revised",
       "selective_consistent_no_amp":"V-R0 Revised without amplification",
       "adaptive_consistent":"V-A Context selective revised", "quota_fixed":"Q-F Fixed quotas",
       "quota_context":"Q-A Context quotas", "uniform_fifo":"FIFO Global recency"}


def value(scenario,policy,error=0):
    return 100*summary[scenario,error,policy]["recall_mean"]


def table(headers,rows,caption):
    return caption+"\n\n| "+" | ".join(headers)+" |\n|"+"|".join("---" for _ in headers)+"|\n"+"\n".join(
        "| "+" | ".join(str(x) for x in row)+" |" for row in rows)


def main():
    rows=[
        ["U-L","Uniform λ=0.6875","Legacy amplified interval","Fixed"],
        ["V-L","Selective Λ=(0.05,0.9,0.9,0.9)","Legacy amplified interval","Fixed"],
        ["U-R","Uniform λ=0.6875","Raw score interval","Fixed"],
        ["V-R","Selective vector as V-L","Raw score interval","Fixed"],
        ["V-R0","As V-R with δ_max=0","Raw score interval","Fixed"],
        ["V-A","As V-R with target update","Raw score interval","Target supplied at switch"],
        ["Q-F","128 active slots with domain quotas","No shadow pool","Fixed target prior"],
        ["Q-A","Same quotas and total budget","No shadow pool","Same switch signal as V-A"],
        ["FIFO","128 active FIFO slots","No shadow pool","No target specialization"],
    ]
    replacements={
      "POLICY_TABLE":table(["Code","Admission or allocation","Archival","Context"],rows,"Table 1. Policies and equal-information controls."),
      "FOCUS_SELECTIVE":f"{value('focused','selective_consistent'):.2f}%",
      "FOCUS_UNIFORM":f"{value('focused','uniform_consistent'):.2f}%",
      "FOCUS_QUOTA":f"{value('focused','quota_fixed'):.2f}%",
      "SHIFT_ADAPTIVE":f"{value('shifted','adaptive_consistent'):.2f}%",
      "SHIFT_QUOTA":f"{value('shifted','quota_context'):.2f}%",
      "SHIFT_FIXED":f"{value('shifted','selective_consistent'):.2f}%",
      "SHIFT_FIFO":f"{value('shifted','uniform_fifo'):.2f}%",
      "NOISY_ADAPTIVE":f"{value('shifted','adaptive_consistent',.2):.2f}%",
      "NOISY_QUOTA":f"{value('shifted','quota_context',.2):.2f}%",
      "SHADOW_DELTA":f"{value('focused','selective_consistent')-value('focused','selective_legacy'):.2f}",
    }
    for key,error in [("RESULTS_TABLE_CLEAN",0),("RESULTS_TABLE_NOISY",.2)]:
        rows=[[label,*[f"{value(scenario,policy,error):.2f}" for scenario in ("focused","shifted","diffuse")]]
              for policy,label in codes.items()]
        caption=f"Table {2 if error==0 else 3}. Mean Recall@1 (%) across sixteen seeds with {int(error*100)}% ingestion routing error."
        replacements[key]=table(["Policy","Focused","Shifted","Diffuse"],rows,caption)
    rows=[]
    selections=[("focused",0,"selective_consistent","uniform_consistent"),
                ("focused",0,"selective_consistent","selective_legacy"),
                ("focused",0,"selective_consistent","selective_consistent_no_amp"),
                ("focused",0,"selective_consistent","quota_fixed"),
                ("shifted",0,"adaptive_consistent","quota_context"),
                ("shifted",.2,"adaptive_consistent","quota_context")]
    for scenario,error,left,right in selections:
        row=next(r for r in data["contrasts"] if (r["scenario"],r["routing_error"],r["left"],r["right"])==
                 (scenario,error,left,right))
        low,high=row["descriptive_normal_interval"]
        rows.append([f"{codes[left].split()[0]} minus {codes[right].split()[0]}",
                     f"{scenario}, {int(error*100)}% error",f"{row['delta']*100:+.2f}",f"[{low*100:+.2f}, {high*100:+.2f}]"])
    replacements["CONTRAST_TABLE"]=table(["Contrast","Condition","Difference p.p.","Descriptive interval p.p."],
        rows,"Table 4. Paired differences and descriptive normal intervals across seeds.")
    payloads=[round(summary['focused',0,p]['payload_bytes_mean']) for p in
              ['selective_consistent','uniform_consistent','quota_fixed']]
    replacements["CONTRAST_TABLE"] += (f"\n\nIn the focused error-free condition, mean serialized episode payload is "
        f"{payloads[0]:,} bytes for V-R, {payloads[1]:,} for U-R and {payloads[2]:,} for Q-F. "
        "Quota limits leave some slots unused; these are realized payload measurements rather than equal-byte claims.")
    revision_rows=[
        ["Clinical archetypes","Engineering profiles in Sections 3 and 7","Human equivalence not assumed"],
        ["Unrestricted theorem VAL-1","Propositions 1 and 2 in Section 4","Admission and fixed nonnegative score trace only"],
        ["C(S,t) and inverse λ","Failure conditions in Section 4","Removed as consciousness measure"],
        ["H_R amplification","Priority scale in Section 3","Calibratable multiplier only"],
        ["Shadow interval VAL-7","Same-score archival in Equation 5","Legacy rule tested separately"],
        ["Eureka probability","Joint retrieval indicator in Section 3","No independence or creativity inference"],
        ["Value update VAL-9","Projected ascent in Equation 13","External gradients and sign stated"],
        ["Motivational prior","Unresolved extension in Appendix B","No autonomous motivation claimed"],
        ["LoRA and REM phases","Optional plans in Appendix B","Training and generation not executed"],
        ["Fixed numerical predictions","Distribution-dependent quantities","Not reported as verified constants"],
        ["Illustrative architecture figures","Measured retrieval in Figure 1","Proposal imagery not reused as data"],
    ]
    replacements["REVISION_TABLE"]=table(["Earlier element","Revised placement","Scientific status"],revision_rows,
        "Table A1. Structural mapping of the earlier manuscript to this formulation.")
    text=(ROOT/"manuscript/VAL_Revised_Manuscript.template.md").read_text()
    for key,val in replacements.items():
        text=text.replace("{{"+key+"}}",val)
    assert not re.search(r"\{\{[A-Z_]+\}\}",text),"unfilled manuscript placeholder"
    (ROOT/"manuscript/VAL_Revised_Manuscript_2026-11-11.md").write_text(text,encoding="utf-8")
    # Verify the null amplification result at the same seed, not merely rounded means.
    index={(r['scenario'],r['routing_error'],r['seed'],r['policy']):r for r in data['rows']}
    for scenario in ('focused','shifted','diffuse'):
        for error in (0,.2):
            for seed in range(data['settings']['seeds']):
                assert index[scenario,error,seed,'selective_consistent']['recall']==index[scenario,error,seed,'selective_consistent_no_amp']['recall']
    policies=['uniform_consistent','selective_consistent','adaptive_consistent','quota_context','uniform_fifo']
    labels=['Uniform revised','Selective revised','Context selective','Context quotas','Global FIFO']
    colors=['#666666','#2166ac','#1b7837','#b35806','#8073ac']
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(10.2,4.1),sharey=True)
    for ax,error in zip(axes,(0,.2)):
        for i,(policy,label,color) in enumerate(zip(policies,labels,colors)):
            r=[summary[s,error,policy] for s in ('focused','shifted','diffuse')]
            ax.bar([j+(i-2)*.16 for j in range(3)], [x['recall_mean']*100 for x in r],
                   width=.15,color=color,label=label,yerr=[x['recall_sd']*100 for x in r],
                   error_kw={'elinewidth':.6,'capsize':1.7})
        ax.set_xticks([0,1,2],['Focused','Shifted','Diffuse'])
        ax.set_title(f"Ingestion routing error {int(error*100)}%",loc='left',fontweight='bold')
        ax.set_ylim(0,108)
        ax.set_yticks([0,20,40,60,80,100])
        ax.grid(axis='y',alpha=.17)
        ax.set_axisbelow(True)
    axes[0].set_ylabel('Recall@1 (%)')
    handles,names=axes[0].get_legend_handles_labels()
    fig.legend(handles,names,loc='lower center',ncol=3,frameon=False,bbox_to_anchor=(.5,-.02))
    fig.tight_layout(rect=(0,.13,1,1))
    fig.savefig(ROOT/'results/revision_comparison.png',dpi=240,bbox_inches='tight',facecolor='white')
    fig.savefig(ROOT/'results/revision_comparison.svg',bbox_inches='tight',facecolor='white')
    plt.close(fig)
    print(json.dumps(dict(manuscript_words=len(text.split()),runs=len(data['rows']),amplification_null_verified=True)))


if __name__=='__main__':
    main()
