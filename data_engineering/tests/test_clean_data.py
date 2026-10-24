import pandas as pd
import pytest

from data_engineering.scripts_etl import clean_data as cd

RAW = """Row ID,Order ID,Order Date,Ship Date,Customer ID,Customer Name,Segment,Region,Product ID,Category,Sub-Category,Product Name,Sales,Quantity,Discount,Profit
1,CA-1,1/5/2016,1/9/2016,cg-1,Claire Gute,consumer, west ,FUR-1,Furniture,Chairs,Chair A,100.5,2,0.1,20
1,CA-1,1/5/2016,1/9/2016,cg-1,Claire Gute,consumer, west ,FUR-1,Furniture,Chairs,Chair A,100.5,2,0.1,20
2,CA-2,2/20/2016,2/25/2016,ab-2,Ali B,CORPORATE,East,TEC-1,Technology,Phones,Phone X,300,1,0,-15
3,CA-3,13/03/2016,,zz-3,Zed Z,Consumer,East,OFF-1,Office Supplies,Paper,Paper,50,0,0,5
4,CA-4,3/15/2016,3/18/2016,zz-4,Zed Y,Consumer,East,OFF-2,Office Supplies,Paper,Paper B,,3,0,5
"""


@pytest.fixture
def raw_csv(tmp_path):
    p = tmp_path / "raw.csv"
    p.write_text(RAW, encoding="latin-1")
    return str(p)


def test_clean_pipeline(raw_csv, tmp_path):
    out = tmp_path / "clean.csv"
    df = cd.clean(raw_csv, str(out), "%m/%d/%Y", str(tmp_path / "report.json"))

    # doublon supprime, quantite 0 supprimee, ventes manquantes supprimees
    assert len(df) == 2
    assert list(df.columns) == cd.FINAL_COLUMNS
    assert df["order_id"].tolist() == ["CA-1", "CA-2"]
    # standardisation
    assert set(df["region"]) == {"West", "East"}
    assert set(df["segment"]) == {"Consumer", "Corporate"}
    assert df["customer_id"].iloc[0] == "CG-1"
    # dates et types
    assert str(df["order_date"].min().date()) == "2016-01-05"
    assert df["quantity"].dtype.kind == "i"
    assert df["profit"].iloc[1] == -15.0  # profit negatif conserve
    assert out.exists()
    assert (tmp_path / "report.json").exists()


def test_date_format_autodetect():
    s = pd.Series(["13/03/2016", "01/04/2016"])
    parsed, fmt = cd.parse_dates(s, "%m/%d/%Y")
    assert fmt == "%d/%m/%Y"
    assert parsed.notna().all()


def test_missing_required_column(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        cd.clean(str(p), str(tmp_path / "o.csv"), report_path=str(tmp_path / "r.json"))
