import requests, re, pandas as pd, streamlit as st
from bs4 import BeautifulSoup
from io import BytesIO

st.title("Ahrefs Traffic Checker (Requests mode)")
file = st.file_uploader("Upload CSV", type=["csv","xlsx"])
if file:
    df = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
    col = st.selectbox("Select URL column", df.columns)
    if st.button("Start"):
        results = []
        for url in df[col]:
            try:
                r = requests.get(f"https://ahrefs.com/traffic-checker/?input={url}&mode=subdomains", timeout=30)
                soup = BeautifulSoup(r.text, "html.parser")
                title = soup.title.text if soup.title else "N/A"
                visits = re.search(r"([\d,\.]+)\s+visits", r.text, re.I)
                traffic = visits.group(1) if visits else "N/A"
                results.append({"URL": url, "Title": title, "Traffic": traffic, "Status": "Success"})
            except Exception as e:
                results.append({"URL": url, "Title": "Error", "Traffic": "N/A", "Status": str(e)[:80]})
        res = pd.DataFrame(results)
        st.dataframe(res)
        buf = BytesIO(); res.to_csv(buf,index=False)
        st.download_button("Download CSV", buf.getvalue(), "results.csv", "text/csv")
