"""시계열 예측 - Prophet 및 ARIMA."""

import logging

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class Forecaster:
    """동별 실거래가, 매출 등의 시계열 예측."""

    def __init__(self, method: str = "prophet"):
        """
        Args:
            method: "prophet" or "arima"
        """
        self.method = method

    def forecast(
        self,
        df: pd.DataFrame,
        date_col: str = "연월",
        value_col: str = "평균거래금액",
        periods: int = 12,
    ) -> pd.DataFrame:
        """시계열 예측.

        Args:
            df: 시계열 데이터 (날짜, 값)
            date_col: 날짜 컬럼
            value_col: 예측할 값 컬럼
            periods: 예측 기간 (월)

        Returns:
            예측 결과 DataFrame
        """
        if self.method == "prophet":
            return self._forecast_prophet(df, date_col, value_col, periods)
        else:
            return self._forecast_arima(df, date_col, value_col, periods)

    def _forecast_prophet(
        self, df: pd.DataFrame, date_col: str, value_col: str, periods: int
    ) -> pd.DataFrame:
        """Prophet으로 예측."""
        try:
            from prophet import Prophet
        except ImportError:
            logger.warning("prophet 미설치, ARIMA로 대체")
            return self._forecast_arima(df, date_col, value_col, periods)

        prophet_df = df[[date_col, value_col]].rename(
            columns={date_col: "ds", value_col: "y"}
        )
        prophet_df["ds"] = pd.to_datetime(prophet_df["ds"])
        prophet_df = prophet_df.dropna()

        if len(prophet_df) < 3:
            return pd.DataFrame()

        model = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
        model.fit(prophet_df)

        future = model.make_future_dataframe(periods=periods, freq="MS")
        forecast = model.predict(future)

        result = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].rename(columns={
            "ds": "날짜",
            "yhat": "예측값",
            "yhat_lower": "하한",
            "yhat_upper": "상한",
        })
        result["실제값"] = None
        result.loc[result.index[:len(prophet_df)], "실제값"] = prophet_df["y"].values
        return result

    def _forecast_arima(
        self, df: pd.DataFrame, date_col: str, value_col: str, periods: int
    ) -> pd.DataFrame:
        """statsmodels ARIMA로 예측."""
        try:
            from statsmodels.tsa.arima.model import ARIMA
        except ImportError:
            logger.error("statsmodels 미설치")
            return pd.DataFrame()

        ts = df[[date_col, value_col]].dropna()
        ts[date_col] = pd.to_datetime(ts[date_col])
        ts = ts.set_index(date_col).sort_index()

        if len(ts) < 5:
            return pd.DataFrame()

        try:
            model = ARIMA(ts[value_col], order=(1, 1, 1))
            fit = model.fit()
            forecast = fit.forecast(steps=periods)

            future_dates = pd.date_range(
                start=ts.index[-1] + pd.DateOffset(months=1),
                periods=periods,
                freq="MS",
            )

            result = pd.DataFrame({
                "날짜": list(ts.index) + list(future_dates),
                "실제값": list(ts[value_col].values) + [None] * periods,
                "예측값": [None] * len(ts) + list(forecast.values),
            })
            return result

        except Exception:
            logger.exception("ARIMA 예측 실패")
            return pd.DataFrame()

    def forecast_by_dong(
        self,
        df: pd.DataFrame,
        dong_codes: list[str],
        date_col: str = "연월",
        value_col: str = "평균거래금액",
        periods: int = 12,
    ) -> dict[str, pd.DataFrame]:
        """여러 행정동의 예측 일괄 실행."""
        results = {}
        for code in dong_codes:
            dong_df = df[df["행정동코드"] == code]
            if dong_df.empty:
                continue
            try:
                results[code] = self.forecast(dong_df, date_col, value_col, periods)
            except Exception:
                logger.exception("예측 실패: %s", code)
        return results
