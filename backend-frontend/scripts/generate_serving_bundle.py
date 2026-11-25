"""Build the Go serving bundle from Syed's audited artifacts."""
from __future__ import annotations
import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "model" / "artifacts"
DATA = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw" / "KuaiRec"
OUT = Path(__file__).resolve().parents[1] / "backend" / "serving_data"

def load(name): return json.loads((ART / name).read_text(encoding="utf-8"))
def metrics(row):
    m=row["metrics"]
    return {"recall_at_10":m["recall@10"],"recall_at_20":m["recall@20"],"ndcg_at_10":m["ndcg@10"],"ndcg_at_20":m["ndcg@20"],"hit_rate_at_10":m["hit_rate@10"],"hit_rate_at_20":m["hit_rate@20"],"precision_at_10":m["precision@10"],"precision_at_20":m["precision@20"],"catalog_coverage":row.get("catalog_coverage@20",row.get("catalog_coverage_at_20",row.get("catalog_coverage_at_max_k",0)))}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    model=load("model_manifest.json"); hybrid=load("hybrid_validation_metrics.json")
    pop=load("popularity_validation_metrics.json"); item=load("item_cf_validation_metrics.json"); light=load("lightgcn_validation_metrics.json"); test=load("controlled_test_metrics.json")
    pop_model=load("popularity_model.json"); pop_counts={str(x["video_id"]):int(x["score"]) for x in pop_model["items"]}
    metadata={}
    meta_path=RAW/"kuairec_caption_category.csv"
    if meta_path.exists():
        with meta_path.open(encoding="utf-8",newline="") as f:
            for r in csv.DictReader(f): metadata[r["video_id"]]=r
    catalog=[]
    with (DATA/"candidate_catalog.csv").open(newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            i=r["video_id"]; md=metadata.get(i,{})
            title=(md.get("caption") or md.get("manual_cover_text") or f"KuaiRec Video {i}").strip()
            if not title or title=="UNKNOWN": title=f"KuaiRec Video {i}"
            catalog.append({"item_id":i,"title":title[:160],"category":md.get("first_level_category_name") or "Uncategorized","duration_seconds":0,"tags":[],"author_id":"","upload_date":"","watch_ratio_avg":0,"total_views":pop_counts.get(i,0)})
    (OUT/"catalog.json").write_text(json.dumps(catalog,ensure_ascii=False),encoding="utf-8")

    recommendations={}
    with (ART/"controlled_test_predictions.csv").open(newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            i=r["video_id"]
            recommendations.setdefault(r["user_id"],[]).append({"item_id":i,"rank":int(r["rank"]),"score":float(r["hybrid_score"]),"source":"hybrid-validation-selected-v1","reasons":[{"code":"popular_in_training","text":"Popular in positive training interactions.","evidence":{"positive_training_event_count":pop_counts.get(i,0),"popularity_weight":0.1}}]})
    (OUT/"recommendations.json").write_text(json.dumps(recommendations,separators=(",",":")),encoding="utf-8")

    comparison={}
    sources={"popularity-positive-event-count-v1":"popularity_validation_predictions.csv","item-cf-cosine-v1":"item_cf_validation_predictions.csv","lightgcn-validation-selected-v1":"lightgcn_validation_predictions.csv","hybrid-validation-selected-v1":"hybrid_validation_predictions.csv"}
    demo_users=set(list(recommendations)[:100])
    for model_id,name in sources.items():
        by={}
        with (ART/name).open(newline="",encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["user_id"] not in demo_users: continue
                score=float(r.get("hybrid_score",r.get("score",0)))
                by.setdefault(r["user_id"],[]).append({"item_id":r["video_id"],"rank":int(r["rank"]),"score":score,"source":model_id,"reasons":[]})
        comparison[model_id]=by
    (OUT/"comparisons.json").write_text(json.dumps(comparison,separators=(",",":")),encoding="utf-8")

    models=[
      {"id":"popularity-positive-event-count-v1","name":"Popularity baseline","type":"baseline","description":"Positive training-event count; cold-start fallback.","is_fallback":True,"metrics":metrics(pop)},
      {"id":"item-cf-cosine-v1","name":"Item-CF","type":"collaborative","description":"Validation-tuned cosine Item-CF.","is_fallback":False,"metrics":metrics(item)},
      {"id":"lightgcn-validation-selected-v1","name":"LightGCN (rejected experiment)","type":"experimental","description":"Evaluated on validation and assigned zero final weight.","is_fallback":False,"metrics":metrics(light["validation"])},
      {"id":"hybrid-validation-selected-v1","name":"Selected hybrid","type":"hybrid","description":"Frozen 0.1 popularity + 0.9 Item-CF + 0.0 LightGCN.","is_fallback":False,"weights":{"alpha_cf":0.9,"beta_extension":0.0,"gamma_popularity":0.1},"metrics":metrics(hybrid["full_validation"])}]
    manifest={"manifest_version":"1.0","generated_at":model["generated_at_utc"],"dataset_release":{"name":model["dataset"]["release"],"paper":"KuaiRec: A Fully-observed Dataset and Insights for Evaluating Recommender Systems","official_url":"https://zenodo.org/records/18164998","source_repo":"https://github.com/chongminggao/KuaiRec","protocol":model["protocol"]["split"],"target_definition":model["dataset"]["target"]["definition"]},"current_model":"hybrid-validation-selected-v1","models":models,"reason_code_rules":[{"code":"liked_by_similar_users","description":"Item-CF contribution backed by positive history."},{"code":"popular_in_training","description":"Positive training-event count."},{"code":"cold_start","description":"Popularity fallback for unknown/no-positive-history users."}]}
    (OUT/"model_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    summary={"evaluation_protocol":{"dataset":model["dataset"]["release"],"training_split":"chronological 70%","validation_split":"chronological 15%","test_split":"chronological 15%","target_threshold":"watch_ratio > 2.0","candidate_pool":"full eligible catalog minus seen items","evaluation_users_count":test["evaluation"]["users_total"],"catalog_size":model["dataset"]["eligible_items"]},"overall_metrics":models,"controlled_test":{"model_id":test["model_id"],**metrics(test["evaluation"]),"users_metric_eligible":test["evaluation"]["users_metric_eligible"],"users_without_eligible_relevant_item":test["evaluation"]["users_without_eligible_relevant_item"]}}
    (OUT/"metrics_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    (OUT/"popularity.json").write_text(json.dumps([str(x["video_id"]) for x in pop_model["items"]]),encoding="utf-8")
    print(json.dumps({"catalog":len(catalog),"users":len(recommendations),"recommendations":sum(map(len,recommendations.values())),"models":len(models)},indent=2))
if __name__=="__main__": main()
