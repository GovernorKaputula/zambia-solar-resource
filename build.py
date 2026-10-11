"""Build an offline-capable explorer from computed results; no live API at runtime."""
import html
import json
import os
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent
ORIGIN = os.environ.get("SOLAR_ORIGIN", "https://governorkaputula.github.io/zambia-solar-resource").rstrip("/")


def main():
    data = json.loads((ROOT / "reports/explorer.json").read_text(encoding="utf-8"))
    metrics = data["summary"]
    options = ''.join(f'<option value="{c["name"]}">{c["name"]}</option>' for c in data["cities"])
    content = (ROOT / "website/index.html").read_text(encoding="utf-8")
    replacements = {"__ORIGIN__": ORIGIN, "__OPTIONS__": options, "__COMPARE_OPTIONS__": options,
                    "__MODEL_MAE__": f'{metrics["test"]["mae"]:.3f}', "__BASELINE_MAE__": f'{metrics["baseline"]["mae"]:.3f}',
                    "__COVERAGE__": f'{metrics["coverage"]*100:.1f}',
                    "__VALIDATION_ROWS__": ''.join(f'<tr><th scope="row">{html.escape(name.replace("_", " "))}</th><td>{value:.4f}</td></tr>' for name,value in metrics["validation_leaderboard"].items()),
                    "__STUDY_DATA__": json.dumps(data, ensure_ascii=False).replace("</", "<\\/")}
    seasons = {s["season"]: s for s in metrics["seasons"]}
    skill = metrics["skill_pct"]
    replacements.update({
        "__RELATIVE_ERROR__": f'{abs(skill):.2f}% {"higher" if skill < 0 else "lower"}',
        "__SKILL_INTERVAL__": ' and '.join(f'{v:+.2f}%' for v in metrics["skill_95_block_interval"]),
        "__DRY_COVERAGE__": f'{seasons["May-Oct"]["coverage"]*100:.1f}',
        "__WET_COVERAGE__": f'{seasons["Nov-Apr"]["coverage"]*100:.1f}',
    })
    for key, value in replacements.items():
        content = content.replace(key, value)
    for name in ["docs", "dist"]:
        output = ROOT / name
        output.mkdir(exist_ok=True)
        (output / "index.html").write_text(content, encoding="utf-8")
        (output / ".nojekyll").write_text("")
        (output / "favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#193e36"/><circle cx="32" cy="32" r="15" fill="#d6b476"/></svg>')
        for asset in ["styles.css", "app.js"]:
            shutil.copy2(ROOT / "website" / asset, output / asset)
        shutil.copytree(ROOT / "reports", output / "reports", dirs_exist_ok=True)
        (output / "data").mkdir(exist_ok=True)
        shutil.copy2(ROOT / "data/daily.csv", output / "data/daily.csv")
        (output / "downloads").mkdir(exist_ok=True)
        with zipfile.ZipFile(output / "downloads/source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            files = [ROOT / f for f in ["README.md", "requirements.txt", "build.py", ".gitignore", ".gitattributes", "LICENSE", "DATA_SOURCES.md", "CONTRIBUTING.md", "CITATION.cff"] if (ROOT / f).is_file()]
            for folder in ["src", "data", "reports", "tests", "scripts", "sql", "website", ".github"]:
                files.extend(p for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
            for file in sorted(files):
                archive.write(file, file.relative_to(ROOT).as_posix())
    print("Built the solar explorer into docs/ and dist/.")


if __name__ == "__main__":
    main()
