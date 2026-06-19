def clean_data(df):
    df["price"] = df["price"].str.replace("Â£", "£")
    df["stock"] = df["stock"].str.replace("\n", " ").str.strip()
    return df
