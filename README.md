# NewsforPrediction

電源・燃料価格予測に影響しそうな外部要因を、朝会向けの Markdown ブリーフィングにまとめるための小さなエージェント実装です。

## できること

- 原油、LNG、石炭、為替、国内電力価格の前日比・週次変化を整理
- 気温予報、需要、発電所停止・再稼働、ニュースを同時に評価
- 異常変動の検知
- 価格予測への上振れ/下振れ要因の候補抽出
- 「今日見るべきデータ」「判断保留すべき点」の自動列挙
- 指定フォーマットの Markdown 出力

## 実行

```powershell
python main.py --input sample_input.json
```

公式無料ソースから自動取得して生成する場合:

```powershell
python main.py --official-free-config sample_free_config.json
```

または `--input` に設定ファイルを渡しても自動判別します:

```powershell
python main.py --input sample_free_config.json
```

`briefing_date` を省略した場合は、`Asia/Tokyo` の実行日が自動で使われます。

Markdown をファイル保存したい場合:

```powershell
python main.py --input sample_input.json --output briefing.md
```

## 入力形式

サンプルは [sample_input.json](/c:/Users/石井悠翔/dev/yukitomo_ana/ITS_Diggup/NewsforPrediction/sample_input.json) を参照してください。

大枠は以下です。

```json
{
  "briefing_date": "2026-06-15",
  "metrics": [
    {
      "name": "JKM",
      "category": "fuel",
      "current": 12.8,
      "previous": 12.1,
      "week_ago": 11.4,
      "unit": "USD/MMBtu",
      "higher_means": "up",
      "abnormal_daily_pct_threshold": 4.0
    }
  ],
  "weather": {
    "region": "Tokyo",
    "forecast_temp_c": 30.0,
    "previous_forecast_temp_c": 28.5,
    "normal_temp_c": 27.0,
    "sensitivity_mode": "cooling"
  },
  "demand": {
    "forecast_gw": 94.0,
    "previous_forecast_gw": 90.0,
    "week_ago_forecast_gw": 88.0
  },
  "plant_events": [],
  "news_events": []
}
```

## テスト

```powershell
python -m unittest discover -s tests -v
```

## 設計メモ

- データ取得 API はまだ固定していません
- 現状は「集めたデータを朝会フォーマットへ変換する分析エンジン」です
- 将来は `metrics` や `news_events` を埋めるコネクタ層を追加すれば、そのまま自動化できます

## 公式無料ソース PoC

`sample_free_config.json` を使うと、以下の公式無料ソースをもとに入力を自動生成します。

- JEPX
- OCCTO
- 気象庁
- BOJ
- 資源エネルギー庁
- NRA

注意:

- 前日比・週次変化は `data/history.json` のローカル履歴も使って計算します
- 初回実行では履歴不足のため、一部指標が「判断保留」になります
- BOJ の USD/JPY は公式ページが PDF / 時系列検索中心のため、PoC では数値取得に失敗した場合は未確認扱いに落とします
- 原油・LNG・石炭の数値価格は、この無料公式ソース構成では直接は取っていません。現状は資源エネルギー庁の制度・需給ニュースを代理情報として扱います
