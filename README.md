Встановити requirements.txt у cmd/powershell
python -m pip install -r requirements.txt
Встановити python 3.2, скопіювати та запустити код
# Order Blocks Indicator

## Опис проєкту

Проєкт реалізує технічний індикатор Order Blocks мовою Python на основі індикатора, написаного мовою PineScript для платформи TradingView.

Програма завантажує історичні ринкові дані активу BTC-USD за допомогою бібліотеки `yfinance`, розраховує технічні індикатори EMA, SMA, VWMA та RSI, визначає зони Order Blocks і BOS-свічки, після чого будує японський свічковий графік за допомогою `mplfinance`.

## Використані бібліотеки

- `yfinance` — завантаження історичних ринкових даних;
- `pandas` — обробка табличних даних та розрахунок індикаторів;
- `mplfinance` — побудова японських свічкових графіків;
- `matplotlib` — графічне відображення результатів.

## Структура проєкту

```git
│
├── ind.py
├── requirements.txt
├── README.md
│
├── screenshots/
│   ├── python_chart.png
│   └── trading_view.png
│
└── uml/
    ├── use_case_diagram.png
    ├── class_diagram.png
    └── sequence_diagram.png