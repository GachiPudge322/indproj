"""
Програма реалізує технічний індикатор Order Blocks мовою Python.

Скрипт завантажує історичні ринкові дані через yfinance, розраховує
технічні індикатори EMA, SMA, VWMA, RSI, визначає зони Order Blocks,
BOS-свічки та будує японський свічковий графік.
"""

from dataclasses import dataclass
from typing import List

import pandas as pd
import yfinance as yf
import mplfinance as mpf


@dataclass
class OrderBlock:
    """
    Клас описує одну зону Order Block.

    Attributes:
        index: Індекс свічки, де було знайдено зону.
        top: Верхня межа зони.
        bottom: Нижня межа зони.
        block_type: Тип зони: bullish або bearish.
    """

    index: int
    top: float
    bottom: float
    block_type: str


class OrderBlocksProgram:
    """
    Основний клас програми.

    Клас відповідає за завантаження ринкових даних, розрахунок
    технічних індикаторів, створення торгових сигналів, пошук
    Order Blocks та побудову графіка.
    """

    def __init__(
        self,
        ticker: str = "BTC-USD",
        start_date: str = "2025-12-01",
        end_date: str = "2026-05-01",
        interval: str = "1d",
        candle_range: int = 15
    ) -> None:
        """
        Ініціалізує налаштування програми.

        Args:
            ticker: Назва активу для завантаження даних.
            start_date: Початкова дата періоду.
            end_date: Кінцева дата періоду.
            interval: Таймфрейм свічок.
            candle_range: Кількість свічок для визначення структури ринку.
        """

        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.interval = interval
        self.candle_range = candle_range

        self.bullish_blocks: List[OrderBlock] = []
        self.bearish_blocks: List[OrderBlock] = []

    def load_data(self) -> pd.DataFrame:
        """
        Завантажує історичні OHLCV-дані з Yahoo Finance.

        Returns:
            pd.DataFrame: Таблиця з колонками Open, High, Low, Close, Volume.

        Raises:
            ValueError: Якщо дані не були завантажені.
        """

        data = yf.download(
            self.ticker,
            start=self.start_date,
            end=self.end_date,
            interval=self.interval,
            auto_adjust=False,
            progress=False
        )

        if data.empty:
            raise ValueError("Дані не були завантажені.")

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        return data[["Open", "High", "Low", "Close", "Volume"]].dropna()

    def add_strategy_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Додає до таблиці технічні індикатори торгової стратегії.

        Розраховуються EMA(12), SMA(40), VWMA(12) та RSI(40).

        Args:
            data: Таблиця з ринковими даними.

        Returns:
            pd.DataFrame: Таблиця з доданими технічними індикаторами.
        """

        data = data.copy()

        data["EMA_12"] = data["Close"].ewm(span=12, adjust=False).mean()
        data["SMA_40"] = data["Close"].rolling(window=40).mean()

        price_volume = data["Close"] * data["Volume"]
        volume_sum = data["Volume"].rolling(window=12).sum()
        data["VWMA_12"] = price_volume.rolling(window=12).sum() / volume_sum

        delta = data["Close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=40).mean()
        avg_loss = loss.rolling(window=40).mean()

        rs = avg_gain / avg_loss
        data["RSI_40"] = 100 - (100 / (1 + rs))

        return data

    def add_trading_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Формує торгові сигнали LONG, SHORT або NONE.

        Умови LONG:
        EMA(12) перетинає знизу вверх VWMA(12);
        SMA(40) > EMA(12);
        RSI(40) < 30.

        Умови SHORT:
        EMA(12) перетинає зверху вниз VWMA(12);
        SMA(40) < EMA(12);
        RSI(40) > 70.

        Args:
            data: Таблиця з розрахованими індикаторами.

        Returns:
            pd.DataFrame: Таблиця з колонкою Signal.
        """

        data = data.copy()
        data["Signal"] = "NONE"

        for i in range(1, len(data)):
            ema_prev = data["EMA_12"].iloc[i - 1]
            ema_now = data["EMA_12"].iloc[i]

            vwma_prev = data["VWMA_12"].iloc[i - 1]
            vwma_now = data["VWMA_12"].iloc[i]

            sma_now = data["SMA_40"].iloc[i]
            rsi_now = data["RSI_40"].iloc[i]

            if pd.isna(ema_now) or pd.isna(vwma_now) or pd.isna(sma_now) or pd.isna(rsi_now):
                continue

            crossover = ema_prev <= vwma_prev and ema_now > vwma_now
            crossunder = ema_prev >= vwma_prev and ema_now < vwma_now

            if crossover and sma_now > ema_now and rsi_now < 30:
                data.loc[data.index[i], "Signal"] = "LONG"

            elif crossunder and sma_now < ema_now and rsi_now > 70:
                data.loc[data.index[i], "Signal"] = "SHORT"

        return data

    def calculate_order_blocks(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Обчислює Order Blocks та BOS-свічки.

        StructureLow визначається як мінімальне значення Low за попередній
        діапазон свічок. Якщо ціна пробиває структуру вниз, створюється
        bearish Order Block. Якщо ціна закривається вище bearish-блоку,
        створюється bullish Order Block.

        Args:
            data: Таблиця з ринковими даними та індикаторами.

        Returns:
            pd.DataFrame: Таблиця з колонками StructureLow, CandleColor та BOS.
        """

        data = data.copy()

        data["StructureLow"] = data["Low"].rolling(self.candle_range).min().shift(1)
        data["CandleColor"] = "red"
        data["BOS"] = False

        last_down_index = 0
        last_down_high = 0.0
        last_down_low = 0.0

        last_up_index = 0
        last_up_high = 0.0
        last_up_low = 0.0

        current_trend = "bearish"

        for i in range(self.candle_range, len(data)):
            open_price = float(data["Open"].iloc[i])
            high_price = float(data["High"].iloc[i])
            low_price = float(data["Low"].iloc[i])
            close_price = float(data["Close"].iloc[i])
            structure_low = data["StructureLow"].iloc[i]

            if pd.isna(structure_low):
                continue

            bos_candle = False

            if low_price < float(structure_low):
                if last_up_index != 0:
                    self.bearish_blocks.append(
                        OrderBlock(
                            index=last_up_index,
                            top=last_up_high,
                            bottom=last_up_low,
                            block_type="bearish"
                        )
                    )

                    current_trend = "bearish"
                    bos_candle = True

            for block in self.bearish_blocks[:]:
                if close_price > block.top:
                    self.bearish_blocks.remove(block)

                    if last_down_index != 0:
                        self.bullish_blocks.append(
                            OrderBlock(
                                index=last_down_index,
                                top=last_down_high,
                                bottom=last_down_low,
                                block_type="bullish"
                            )
                        )

                        current_trend = "bullish"
                        bos_candle = True

            for block in self.bullish_blocks[:]:
                if close_price < block.bottom:
                    self.bullish_blocks.remove(block)

            if bos_candle:
                data.loc[data.index[i], "CandleColor"] = "yellow"
                data.loc[data.index[i], "BOS"] = True
            elif current_trend == "bullish":
                data.loc[data.index[i], "CandleColor"] = "green"
            else:
                data.loc[data.index[i], "CandleColor"] = "red"

            if close_price < open_price:
                last_down_index = i
                last_down_high = high_price
                last_down_low = low_price

            if close_price > open_price:
                last_up_index = i
                last_up_high = high_price
                last_up_low = low_price

        return data

    def show_chart(self, data: pd.DataFrame) -> None:
        """
        Будує японський свічковий графік з індикаторами та Order Blocks.

        Args:
            data: Таблиця з усіма розрахованими даними.
        """

        market_colors = mpf.make_marketcolors(
            up="green",
            down="red",
            edge="inherit",
            wick="inherit",
            volume="inherit"
        )

        style = mpf.make_mpf_style(
            base_mpf_style="yahoo",
            marketcolors=market_colors
        )

        add_plots = [
            mpf.make_addplot(data["EMA_12"], width=1),
            mpf.make_addplot(data["VWMA_12"], width=1),
            mpf.make_addplot(data["SMA_40"], width=1),
        ]

        figure, axes = mpf.plot(
            data,
            type="candle",
            style=style,
            volume=True,
            addplot=add_plots,
            title=f"{self.ticker} Order Blocks Indicator",
            ylabel="Price",
            ylabel_lower="Volume",
            figsize=(14, 8),
            returnfig=True
        )

        price_axis = axes[0]

        for block in self.bullish_blocks:
            price_axis.axhspan(
                block.bottom,
                block.top,
                xmin=block.index / len(data),
                xmax=1,
                alpha=0.15,
                color="green"
            )

        for block in self.bearish_blocks:
            price_axis.axhspan(
                block.bottom,
                block.top,
                xmin=block.index / len(data),
                xmax=1,
                alpha=0.15,
                color="red"
            )

        mpf.show()

    def print_result(self, data: pd.DataFrame) -> None:
        """
        Виводить основні результати роботи програми у консоль.

        Args:
            data: Таблиця з розрахованими значеннями.
        """

        print("\nОстанні значення індикатора:")
        print(
            data[
                [
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "StructureLow",
                    "CandleColor",
                    "BOS",
                    "Signal"
                ]
            ].tail()
        )

        print("\nЗнайдено bullish order blocks:", len(self.bullish_blocks))
        print("Знайдено bearish order blocks:", len(self.bearish_blocks))

        signals = data[data["Signal"] != "NONE"][["Close", "Signal"]]

        print("\nОстанні торгові сигнали:")
        if signals.empty:
            print("Сигналів не знайдено.")
        else:
            print(signals.tail())

    def run(self) -> None:
        """
        Запускає повний цикл роботи програми.
        """

        data = self.load_data()
        data = self.add_strategy_indicators(data)
        data = self.add_trading_signals(data)
        data = self.calculate_order_blocks(data)

        self.print_result(data)
        self.show_chart(data)


def main() -> None:
    """
    Точка входу в програму.
    """

    program = OrderBlocksProgram()
    program.run()


if __name__ == "__main__":
    main()