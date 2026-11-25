"""Generate the local English display dictionary from the frozen catalog."""
import json
from pathlib import Path
import re

import torch
from transformers import MarianMTModel, MarianTokenizer

ROOT = Path(__file__).resolve().parents[1]
MODEL = "Helsinki-NLP/opus-mt-zh-en"
HAN = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\U00020000-\U000323af]")
OUTPUT = ROOT / "frontend/public/catalog-english.local.json"


def main():
    catalog = json.loads((ROOT / "backend/serving_data/catalog.json").read_text(encoding="utf-8"))
    text = {value.strip() for video in catalog for value in (
        video["title"], video["category"], *video["categories"], *video["tags"], video["video_type"]
    ) if HAN.search(value)}
    translations = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    translations = {source: value for source, value in translations.items() if source in text and value and not HAN.search(value)}
    # Reviewed captions and category names used in the live demo.
    reviewed = {
        "旅游": "Travel",
        "旅游玩法": "Travel activities",
        "风景航拍": "Aerial scenery",
        "二次元": "Anime and cosplay culture",
        "二次元真人秀": "Live-action anime and cosplay",
        "汉服古风": "Hanfu and traditional Chinese style",
    }
    demo_captions = {
        "3289": "After a long wait, I finally caught it on camera! The train blows its horn every time it crosses the bridge. Why? #Guizhou",
        "10434": "The director talks Xiao Rui through the scene. Your favorite Xiao Rui is great at acting, too! When does school start for everyone? #Hanfu #SongXiaoRui #HezeKaiLaixi",
    }
    for video in catalog:
        if video["item_id"] in demo_captions:
            reviewed[video["title"].strip()] = demo_captions[video["item_id"]]
    translations.update({source: value for source, value in reviewed.items() if source in text})
    pending = sorted(text - translations.keys(), key=lambda value: (len(value), value))
    save(translations)
    if pending:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Translating {len(pending)} distinct values on {device}", flush=True)
        tokenizer = MarianTokenizer.from_pretrained(MODEL)
        model = MarianMTModel.from_pretrained(MODEL).to(device).eval()
        if device == "cuda":
            model.half()

        with torch.inference_mode():
            for offset in range(0, len(pending), 32):
                batch = pending[offset:offset + 32]
                inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=512).to(device)
                outputs = model.generate(**inputs, num_beams=1, max_new_tokens=256)
                for source, translated in zip(batch, tokenizer.batch_decode(outputs, skip_special_tokens=True), strict=True):
                    translated = translated.strip()
                    if translated and not HAN.search(translated):
                        translations[source] = translated
                if offset % 512 == 0:
                    save(translations)
                    print(f"Processed {min(offset + len(batch), len(pending))}/{len(pending)}", flush=True)

    save(translations)
    print(f"English coverage: {len(translations)}/{len(text)} Chinese-bearing catalog values")


def save(translations):
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(translations, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    temporary.replace(OUTPUT)


if __name__ == "__main__":
    main()
