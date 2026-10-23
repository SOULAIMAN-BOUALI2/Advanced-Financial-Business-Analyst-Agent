"""DEV ONLY: temporary stand-in for Member 1's data_engineering/analytics.py.

workflow.py uses the real analytics module when it exists and falls back to
this file otherwise. Signatures follow the project brief.
"""
import plotly.express as px


def plot_line_chart(df, x, y):
    return px.line(df, x=x, y=y, title=f"{y} by {x}", markers=True)


def plot_bar_chart(df, x, y):
    return px.bar(df, x=x, y=y, title=f"{y} by {x}")


def plot_pie_chart(df, labels, values):
    return px.pie(df, names=labels, values=values, title=f"{values} by {labels}")
