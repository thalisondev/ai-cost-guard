import statistics
import pandas as pd


def detect_anomalies(df: pd.DataFrame, z_threshold: float = 2.5) -> pd.DataFrame:
    anomalies = []

    for user_id, group in df.groupby("user_id"):
        costs = group["cost_usd"].tolist()

        if len(costs) < 5:
            continue

        mean = statistics.mean(costs)
        stdev = statistics.stdev(costs)

        if stdev == 0:
            continue

        for _, row in group.iterrows():
            z_score = (row["cost_usd"] - mean) / stdev
            if z_score > z_threshold:
                anomalies.append({
                    "user_id": user_id,
                    "cost_usd": row["cost_usd"],
                    "user_mean_cost": round(mean, 6),
                    "z_score": round(z_score, 2),
                    "datetime": row["datetime"],
                })

    return pd.DataFrame(anomalies)