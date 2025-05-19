import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
import os

load_dotenv()

# Set page configuration
st.set_page_config(
    page_title="Solana Portfolio Tracker",
    page_icon="💰",
    layout="wide"
)

# App title and description
st.title("Solana Portfolio Tracker")
st.markdown("""
This app tracks your Solana wallet portfolio, showing balances and visualizations of your assets.
""")


# Get API key from environment variables or Streamlit secrets
def get_api_key():
    # First check environment variables
    api_key = os.environ.get("HELIUS_API_KEY")

    # If not in environment variables, check Streamlit secrets
    if not api_key and hasattr(st, "secrets"):
        api_key = st.secrets.get("HELIUS_API_KEY")

    if not api_key:
        st.error("API key not found. Please set HELIUS_API_KEY in environment variables or Streamlit secrets.")
        st.stop()

    return api_key


col1, col2 = st.columns([2, 2])
with col1:
    wallet_address = st.text_input("Wallet Address", "2TWoP4Jzgbpb1PRYUPj9BL5AdWwHECS9EWy6jaWroYM3", placeholder="Enter wallet address here", label_visibility="collapsed")
with col2:
    refresh_button = st.button("Refresh Data")
    if refresh_button:
        st.cache_data.clear()

# Keep sidebar for future expansion if needed
# with st.sidebar:
#     st.header("About")
#     st.info("This application allows you to track your Solana wallet portfolio.")


# Function to fetch wallet data
@st.cache_data(ttl=300)  # Cache data for 5 minutes
def fetch_wallet_data(wallet_address, api_key):
    url = "https://mainnet.helius-rpc.com/"
    querystring = {"api-key": api_key}

    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "getAssetsByOwner",
        "params": {
            "options": {
                "showZeroBalance": False,
                "showNativeBalance": True,
                "showFungible": True
            },
            "ownerAddress": wallet_address
        }
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.request("POST", url, json=payload, headers=headers, params=querystring)
        response.raise_for_status()  # Raise exception for 4XX/5XX errors
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data: {str(e)}")
        return None


# Function to extract portfolio information
def extract_portfolio_info(data):
    if not data:
        return []

    portfolio = []

    # Get SOL native balance info
    if 'result' in data and 'nativeBalance' in data['result']:
        native_balance = data['result']['nativeBalance']
        portfolio.append({
            'name': 'Solana',
            'symbol': 'SOL',
            'total_price_usd': native_balance.get('total_price', 0),
            'amount': native_balance.get('amount', 0),
            'decimals': native_balance.get('decimals', 9)
        })

    # Process items
    if 'result' in data and 'items' in data['result']:
        for item in data['result']['items']:
            # Extract metadata
            name = 'Unknown'
            symbol = 'Unknown'
            total_price = 0
            amount = 0
            decimals = 0

            if 'content' in item and 'metadata' in item['content']:
                metadata = item['content']['metadata']
                name = metadata.get('name', 'Unknown')
                symbol = metadata.get('symbol', 'Unknown')

            # Extract price info for tokens
            if 'interface' in item and item['interface'] == 'FungibleToken':
                if 'token_info' in item:
                    token_info = item['token_info']
                    amount = token_info.get('amount', 0)
                    decimals = token_info.get('decimals', 0)

                    if 'price_info' in token_info:
                        price_info = token_info['price_info']
                        total_price = price_info.get('total_price', 0)

            # Only add items with non-zero price
            if total_price is not None and total_price > 0.5:
                portfolio.append({
                    'name': name,
                    'symbol': symbol,
                    'total_price_usd': total_price,
                    'amount': amount,
                    'decimals': decimals
                })

    return portfolio


# Add a separator for better visual organization
st.markdown("---")

# Main content
if wallet_address:
    # Get API key securely
    api_key = get_api_key()

    with st.spinner("Fetching portfolio data..."):
        data = fetch_wallet_data(
            wallet_address,
            api_key
        )

        if data:
            portfolio = extract_portfolio_info(data)

            if portfolio:
                # Convert to pandas DataFrame for easier manipulation
                df = pd.DataFrame(portfolio)

                # Calculate total portfolio value
                total_portfolio_value = df['total_price_usd'].sum()

                # Display portfolio metrics
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Portfolio Value", f"${total_portfolio_value:,.2f}")
                with col2:
                    st.metric("Number of Assets", f"{len(df)}")

                # Format DataFrame for display
                display_df = df.copy()
                display_df['total_price_usd'] = display_df['total_price_usd'].apply(lambda x: f"${x:,.2f}")
                display_df['formatted_amount'] = display_df.apply(
                    lambda row: f"{float(row['amount']) / (10 ** row['decimals']):,.4f}",
                    axis=1
                )
                st.dataframe(
                    display_df[['name', 'symbol', 'formatted_amount', 'total_price_usd']].rename(
                        columns={
                            'name': 'Asset Name',
                            'symbol': 'Symbol',
                            'formatted_amount': 'Amount',
                            'total_price_usd': 'Value (USD)'
                        }
                    ),
                    use_container_width=True,
                    hide_index=True
                )

                # Create pie chart for portfolio distribution
                if not df.empty:
                    # Filter out very small values for better visualization
                    plot_df = df.copy()
                    threshold = total_portfolio_value * 0.005  # 0.5% threshold
                    small_assets = plot_df[plot_df['total_price_usd'] < threshold]

                    if not small_assets.empty:
                        # Group small assets into "Others"
                        others_row = pd.DataFrame({
                            'name': ['Others'],
                            'symbol': ['VARIOUS'],
                            'total_price_usd': [small_assets['total_price_usd'].sum()],
                        })
                        plot_df = plot_df[plot_df['total_price_usd'] >= threshold]
                        plot_df = pd.concat([plot_df, others_row], ignore_index=True)

                    fig = px.pie(
                        plot_df,
                        values='total_price_usd',
                        names='name',
                        title='Portfolio Distribution',
                        hole=0.4,
                    )
                    fig.update_traces(textinfo='percent+label')
                    st.plotly_chart(fig, use_container_width=True)

            else:
                st.warning("No portfolio data found for this wallet address.")
        else:
            st.error("Failed to fetch wallet data. Please check your API key and wallet address.")
else:
    st.info("Please enter a wallet address to view portfolio data.")

# Add footer
st.markdown("---")
st.markdown("Built with Streamlit and Helius API")
