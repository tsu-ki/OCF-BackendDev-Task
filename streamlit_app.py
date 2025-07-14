import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, date
from typing import Optional
import time
import warnings
import requests

warnings.filterwarnings("ignore")

from ocf_pipeline import elexon_data as ed
from ocf_pipeline.storage import initialize_db, load_dataframe, store_records
import ocf_pipeline.elexon_api as api
from ocf_pipeline.config import DB_PATH


st.set_page_config(
    page_title="UK Renewable Energy Dashboard",
    page_icon="🌟",
    layout="wide",
    initial_sidebar_state="expanded"
)

#CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 5px solid #1f77b4;
    }
    .status-success {
        color: #28a745;
        font-weight: bold;
    }
    .status-warning {
        color: #ffc107;
        font-weight: bold;
    }
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
    .sidebar-header {
        font-size: 1.5rem;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def get_database_status():
    """Get current database status and summary stats."""
    try:
        conn = initialize_db()
        df = load_dataframe(conn)
        conn.close()
        
        if df.empty:
            return {
                'status': 'empty',
                'total_records': 0,
                'date_range': None,
                'technologies': [],
                'latest_data': None
            }
        
        return {
            'status': 'active',
            'total_records': len(df),
            'date_range': (df['start_time'].min(), df['start_time'].max()),
            'technologies': list(df['psr_type'].unique()),
            'latest_data': df['start_time'].max(),
            'dataframe': df
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


def fetch_date_range_with_progress(start_date, end_date):
    """Fetch data for a date range with progress updates."""
    try:
        # Convert dates to datetime
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.min.time())
        
        # Check if range is within API limits
        if (end_dt - start_dt).days > 6:
            return fetch_large_date_range(start_dt, end_dt)
        
        # Single API call for small ranges
        progress_bar = st.progress(0)
        status_container = st.empty()
        
        status_container.info(f"📡 Fetching data from {start_date} to {end_date}")
        progress_bar.progress(0.3)
        
        # Fetch data
        data = api.fetch_generation_data(start_dt, end_dt)
        progress_bar.progress(0.7)
        
        if data:
            # Store data
            conn = initialize_db()
            store_records(conn, data)
            conn.close()
            
            progress_bar.progress(1.0)
            status_container.success(f"✅ Successfully imported {len(data):,} records")
            
            # Validate the imported data
            validation = validate_import_data(start_date=start_dt, end_date=end_dt)
            show_import_summary(validation)
            
            return True, f"Successfully imported {len(data):,} records"
        else:
            progress_bar.progress(1.0)
            status_container.warning("⚠️ No data returned from API")
            return False, "No data returned from API"
            
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return False, f"Import failed: {str(e)}"


def fetch_large_date_range(start_dt, end_dt):
    """Handle large date ranges by chunking into 7-day windows."""
    try:
        progress_bar = st.progress(0)
        status_container = st.empty()
        records_container = st.empty()
        
        conn = initialize_db()
        current = start_dt
        total_days = (end_dt - start_dt).days + 1
        processed_days = 0
        total_records = 0
        
        status_container.info(f"📊 Processing large date range: {total_days} days")
        
        while current <= end_dt:
            chunk_end = min(current + timedelta(days=6), end_dt)
            
            # Update status
            date_range = f"{current.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}"
            status_container.info(f"📡 Fetching chunk: {date_range}")
            
            try:
                # Fetch chunk
                data = api.fetch_generation_data(current, chunk_end)
                
                if data:
                    store_records(conn, data)
                    total_records += len(data)
                    records_container.success(f"✅ Imported {total_records:,} records so far")
                
            except Exception as chunk_error:
                status_container.warning(f"⚠️ Failed to fetch {date_range}: {str(chunk_error)}")
            
            # Update progress
            processed_days += (chunk_end - current).days + 1
            progress = min(processed_days / total_days, 1.0)
            progress_bar.progress(progress)
            
            current = chunk_end + timedelta(days=1)
            time.sleep(0.2)
        
        conn.close()
        
        # Final status
        progress_bar.progress(1.0)
        status_container.success(f"🎉 Large range import complete! Total records: {total_records:,}")
        
        return True, f"Successfully imported {total_records:,} records"
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return False, f"Large range import failed: {str(e)}"


@st.cache_data
def load_filtered_data(start_date: Optional[str] = None, end_date: Optional[str] = None, 
                      psr_type: Optional[str] = None):
    """Load data with filters applied."""
    try:
        conn = initialize_db()
        df = load_dataframe(conn, start=start_date, end=end_date, psr_type=psr_type)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()


def fetch_year_with_progress(year: int):
    """Fetch data for a year with Streamlit progress updates."""
    try:
        # Initialize database
        conn = initialize_db()
        
        # Calculate date range
        start = datetime(year, 1, 1)
        end = datetime(year, 12, 31)
        current = start
        total_days = (end - start).days + 1
        processed_days = 0
        total_records = 0
        
        # Create progress containers
        progress_bar = st.progress(0)
        status_container = st.empty()
        records_container = st.empty()
        
        status_container.info(f"🚀 Starting import for {year}...")
        
        # Process data in chunks
        while current <= end:
            chunk_end = min(current + timedelta(days=6), end)
            
            # Update status
            date_range = f"{current.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}"
            status_container.info(f"📡 Fetching data: {date_range}")
            
            try:
                # Fetch data from API
                data = api.fetch_generation_data(current, chunk_end)
                
                if data:
                    # Store data
                    store_records(conn, data)
                    total_records += len(data)
                    records_container.success(f"✅ Imported {total_records:,} records so far")
                else:
                    status_container.warning(f"⚠️ No data returned for {date_range}")
                
            except Exception as chunk_error:
                status_container.error(f"❌ Error fetching {date_range}: {str(chunk_error)}")
            
            # Update progress
            processed_days += (chunk_end - current).days + 1
            progress = min(processed_days / total_days, 1.0)
            progress_bar.progress(progress)
            
            # Move to next chunk
            current = chunk_end + timedelta(days=1)
            
            # Small delay to avoid overwhelming the API
            time.sleep(0.2)
        
        conn.close()
        
        # Final status
        progress_bar.progress(1.0)
        status_container.success(f"🎉 Import complete! Total records: {total_records:,}")
        
        # Validate the imported data
        validation = validate_import_data(year=year)
        show_import_summary(validation)
        
        return True, f"Successfully imported {total_records:,} records for {year}"
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return False, f"Import failed: {str(e)}"


def create_time_series_plot(df: pd.DataFrame, title: str = "Generation Over Time"):
    """Create interactive time series plot."""
    if df.empty:
        return None
    
    fig = px.line(df, x='start_time', y='quantity', color='psr_type',
                  title=title,
                  labels={'quantity': 'Generation (MW)', 'start_time': 'Time', 'psr_type': 'Technology'})
    
    fig.update_layout(
        height=500,
        showlegend=True,
        xaxis_title="Time",
        yaxis_title="Generation (MW)",
        hovermode='x unified'
    )
    
    return fig


def create_technology_comparison(df: pd.DataFrame):
    """Create technology comparison charts."""
    if df.empty:
        return None, None
    
    tech_summary = df.groupby('psr_type').agg({
        'quantity': ['mean', 'max', 'sum', 'count']
    }).round(2)
    tech_summary.columns = ['Avg MW', 'Peak MW', 'Total MWh', 'Records']
    tech_summary = tech_summary.reset_index()
    
    # Bar chart for average generation
    fig1 = px.bar(tech_summary, x='psr_type', y='Avg MW',
                  title="Average Generation by Technology",
                  color='Avg MW', color_continuous_scale='viridis')
    fig1.update_layout(height=400)
    
    # Pie chart for total generation share
    fig2 = px.pie(tech_summary, values='Total MWh', names='psr_type',
                  title="Total Generation Share by Technology")
    fig2.update_layout(height=400)
    
    return fig1, fig2, tech_summary


def create_heatmap(df: pd.DataFrame):
    """Create generation heatmap by hour and day."""
    if df.empty:
        return None

    df_copy = df.copy()
    df_copy['hour'] = df_copy['start_time'].dt.hour
    df_copy['day_of_week'] = df_copy['start_time'].dt.day_name()
    
    heatmap_data = df_copy.groupby(['day_of_week', 'hour'])['quantity'].mean().unstack(fill_value=0)
    
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    heatmap_data = heatmap_data.reindex(day_order)
    
    fig = px.imshow(heatmap_data, 
                    title="Average Generation by Hour and Day of Week",
                    labels={'x': 'Hour of Day', 'y': 'Day of Week', 'color': 'Avg Generation (MW)'},
                    aspect='auto')
    fig.update_layout(height=400)
    
    return fig


@st.cache_data(ttl=300)
def check_api_status():
    """Check if the Elexon BMRS API is accessible."""
    try:
        test_start = datetime.now() - timedelta(days=1)
        test_end = datetime.now()
        
        response = requests.get(
            api.BASE_URL,
            params={
                "from": test_start.strftime("%Y-%m-%d"),
                "to": test_end.strftime("%Y-%m-%d"),
                "format": "json"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                return {
                    'status': 'online',
                    'message': 'API is accessible',
                    'response_time': response.elapsed.total_seconds()
                }
        
        return {
            'status': 'error',
            'message': f'API returned status {response.status_code}',
            'response_time': response.elapsed.total_seconds()
        }
        
    except requests.exceptions.Timeout:
        return {
            'status': 'timeout',
            'message': 'API request timed out',
            'response_time': None
        }
    except requests.exceptions.ConnectionError:
        return {
            'status': 'offline',
            'message': 'Cannot connect to API',
            'response_time': None
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'API check failed: {str(e)}',
            'response_time': None
        }


def validate_import_data(year: int = None, start_date: datetime = None, end_date: datetime = None):
    """Validate that imported data looks correct."""
    try:
        conn = initialize_db()
        
        # Build query based on parameters
        if year:
            query = "SELECT COUNT(*) as count, MIN(start_time) as min_date, MAX(start_time) as max_date, COUNT(DISTINCT psr_type) as tech_count FROM generation WHERE start_time LIKE ?"
            params = [f"{year}%"]
        elif start_date and end_date:
            query = "SELECT COUNT(*) as count, MIN(start_time) as min_date, MAX(start_time) as max_date, COUNT(DISTINCT psr_type) as tech_count FROM generation WHERE start_time >= ? AND start_time <= ?"
            params = [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")]
        else:
            query = "SELECT COUNT(*) as count, MIN(start_time) as min_date, MAX(start_time) as max_date, COUNT(DISTINCT psr_type) as tech_count FROM generation"
            params = []
        
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone()
        
        conn.close()
        
        return {
            'record_count': result[0] if result[0] else 0,
            'date_range': (result[1], result[2]) if result[1] and result[2] else None,
            'technology_count': result[3] if result[3] else 0,
            'is_valid': result[0] > 0 and result[3] > 0
        }
        
    except Exception as e:
        return {
            'record_count': 0,
            'date_range': None,
            'technology_count': 0,
            'is_valid': False,
            'error': str(e)
        }


def show_import_summary(validation_result):
    """Display import summary with validation results."""
    if validation_result['is_valid']:
        st.success("✅ Data import validation passed!")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Records Imported", f"{validation_result['record_count']:,}")
        with col2:
            st.metric("Technologies", validation_result['technology_count'])
        with col3:
            if validation_result['date_range']:
                date_span = validation_result['date_range'][1][:10] if validation_result['date_range'][1] else "Unknown"
                st.metric("Latest Data", date_span)
        
        if validation_result['date_range']:
            start, end = validation_result['date_range']
            st.info(f"📅 Data covers: {start[:10]} to {end[:10]}")
    else:
        st.error("❌ Data import validation failed!")
        if 'error' in validation_result:
            st.error(f"Error: {validation_result['error']}")
        else:
            st.warning("No valid data found after import operation")


def main():
    """Main Streamlit application."""
    
    # Header
    st.markdown('<h1 class="main-header">🌟 UK Renewable Energy Dashboard</h1>', unsafe_allow_html=True)
    st.markdown("### Real-time monitoring and analysis of UK wind and solar generation data")
    
    # Sidebar
    st.sidebar.markdown('<h2 class="sidebar-header">🛠️ Controls</h2>', unsafe_allow_html=True)
    
    db_status = get_database_status()
    
    with st.sidebar:
        st.markdown("#### 📊 Database Status")
        if db_status['status'] == 'empty':
            st.markdown('<p class="status-warning">⚠️ Database is empty</p>', unsafe_allow_html=True)
            st.info("Import data using the 'Data Management' section below")
        elif db_status['status'] == 'active':
            st.markdown('<p class="status-success">✅ Database active</p>', unsafe_allow_html=True)
            st.metric("Total Records", f"{db_status['total_records']:,}")
            if db_status['date_range']:
                start_date, end_date = db_status['date_range']
                st.write(f"**Date Range:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
                st.write(f"**Technologies:** {', '.join(db_status['technologies'])}")
        else:
            st.markdown('<p class="status-error">❌ Database error</p>', unsafe_allow_html=True)
            st.error(db_status.get('error', 'Unknown error'))
    
    api_status = check_api_status()
    
    with st.sidebar:
        st.markdown("#### 🌐 API Status")
        if api_status['status'] == 'online':
            st.markdown('<p class="status-success">✅ API is online</p>', unsafe_allow_html=True)
            st.info(f"Response Time: {api_status['response_time']} seconds")
        elif api_status['status'] == 'offline':
            st.markdown('<p class="status-error">❌ API is offline</p>', unsafe_allow_html=True)
            st.error(api_status.get('message', 'Cannot connect to API'))
        else:
            st.markdown('<p class="status-warning">⚠️ API status unknown</p>', unsafe_allow_html=True)
            st.warning(api_status.get('message', 'Unable to determine API status'))
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Dashboard", 
        "📊 Analysis", 
        "🔍 Data Explorer", 
        "⚙️ Data Management", 
        "ℹ️ About"
    ])
    
    with tab1:
        st.header("📈 Real-time Dashboard")
        
        if db_status['status'] != 'active':
            st.warning("No data available. Please import data first using the 'Data Management' tab.")
            return
        
        df = db_status.get('dataframe', pd.DataFrame())
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_generation = df['quantity'].sum()
            st.metric("Total Generation", f"{total_generation:,.0f} MWh")
        
        with col2:
            avg_generation = df['quantity'].mean()
            st.metric("Average Generation", f"{avg_generation:.1f} MW")
        
        with col3:
            peak_generation = df['quantity'].max()
            st.metric("Peak Generation", f"{peak_generation:.1f} MW")
        
        with col4:
            latest_update = df['start_time'].max()
            st.metric("Latest Data", latest_update.strftime('%Y-%m-%d'))
        
        # Recent data visualization
        st.subheader("Recent Generation Trends (Last 7 Days)")
        recent_date = df['start_time'].max() - timedelta(days=7)
        recent_df = df[df['start_time'] >= recent_date]
        
        if not recent_df.empty:
            fig = create_time_series_plot(recent_df, "Recent Generation Trends")
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("Technology Overview")
        fig1, fig2, tech_summary = create_technology_comparison(df)
        
        if fig1 and fig2:
            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(fig1, use_container_width=True)
            with col2:
                st.plotly_chart(fig2, use_container_width=True)
            
            st.subheader("Technology Summary")
            st.dataframe(tech_summary, use_container_width=True)
    
    with tab2:
        st.header("📊 Advanced Analysis")
        
        if db_status['status'] != 'active':
            st.warning("No data available. Please import data first using the 'Data Management' tab.")
            return
        
        df = db_status.get('dataframe', pd.DataFrame())
        
        # Filter controls
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if df['start_time'].dt.date.nunique() > 1:
                date_range = st.date_input(
                    "Select Date Range",
                    value=(df['start_time'].min().date(), df['start_time'].max().date()),
                    min_value=df['start_time'].min().date(),
                    max_value=df['start_time'].max().date()
                )
            else:
                date_range = None
        
        with col2:
            selected_tech = st.selectbox(
                "Select Technology",
                ['All'] + list(df['psr_type'].unique())
            )
        
        with col3:
            analysis_type = st.selectbox(
                "Analysis Type",
                ["Time Series", "Distribution", "Correlation", "Seasonal Patterns"]
            )
        
        # Apply filters
        filtered_df = df.copy()
        if date_range and len(date_range) == 2:
            start_date, end_date = date_range
            filtered_df = filtered_df[
                (filtered_df['start_time'].dt.date >= start_date) & 
                (filtered_df['start_time'].dt.date <= end_date)
            ]
        
        if selected_tech != 'All':
            filtered_df = filtered_df[filtered_df['psr_type'] == selected_tech]
        
        if filtered_df.empty:
            st.warning("No data available for selected filters.")
            return
        
        # Analysis visualizations
        if analysis_type == "Time Series":
            fig = create_time_series_plot(filtered_df, f"Generation Analysis - {selected_tech}")
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        
        elif analysis_type == "Distribution":
            fig = px.histogram(filtered_df, x='quantity', color='psr_type',
                             title="Generation Distribution",
                             labels={'quantity': 'Generation (MW)'})
            st.plotly_chart(fig, use_container_width=True)
        
        elif analysis_type == "Correlation":
            if len(filtered_df['psr_type'].unique()) > 1:
                pivot_df = filtered_df.pivot_table(
                    index='start_time', 
                    columns='psr_type', 
                    values='quantity', 
                    aggfunc='mean'
                ).fillna(0)
                
                corr_matrix = pivot_df.corr()
                fig = px.imshow(corr_matrix, 
                               title="Technology Correlation Matrix",
                               color_continuous_scale='RdBu_r')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Correlation analysis requires multiple technologies.")
        
        elif analysis_type == "Seasonal Patterns":
            fig = create_heatmap(filtered_df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("Statistical Summary")
        summary_stats = filtered_df.groupby('psr_type')['quantity'].describe().round(2)
        st.dataframe(summary_stats, use_container_width=True)
    
    with tab3:
        st.header("🔍 Data Explorer")
        
        if db_status['status'] != 'active':
            st.warning("No data available. Please import data first using the 'Data Management' tab.")
            return
        
        # Data filters
        col1, col2 = st.columns(2)
        
        with col1:
            start_date = st.date_input("Start Date", value=None)
            psr_filter = st.selectbox("Technology Filter", ['All'] + db_status['technologies'])
        
        with col2:
            end_date = st.date_input("End Date", value=None)
            max_rows = st.number_input("Max Rows to Display", min_value=10, max_value=10000, value=1000)
        
        start_str = start_date.strftime('%Y-%m-%d') if start_date else None
        end_str = end_date.strftime('%Y-%m-%d') if end_date else None
        psr_str = psr_filter if psr_filter != 'All' else None
        
        filtered_df = load_filtered_data(start_str, end_str, psr_str)
        
        if not filtered_df.empty:
            st.write(f"**Showing {min(len(filtered_df), max_rows):,} of {len(filtered_df):,} records**")
            
            display_df = filtered_df.head(max_rows)
            st.dataframe(display_df, use_container_width=True)
            
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="📥 Download filtered data as CSV",
                data=csv,
                file_name=f"elexon_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No data found for the selected filters.")
    
    with tab4:
        st.header("⚙️ Data Management")
        
        st.subheader("📥 Import Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Import Full Year**")
            year_to_import = st.number_input("Year", min_value=2015, max_value=2025, value=2023)
            
            if st.button("🚀 Import Year Data", type="primary"):
                with st.container():
                    success, message = fetch_year_with_progress(year_to_import)
                    
                    if success:
                        validation_result = validate_import_data(year=year_to_import)
                        show_import_summary(validation_result)
                        
                        st.success(message)
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Import failed: {message}")
        
        with col2:
            st.write("**Import Date Range**")
            range_start = st.date_input("Start Date", key="range_start")
            range_end = st.date_input("End Date", key="range_end")
            
            if st.button("📊 Import Range Data"):
                if range_start and range_end:
                    if (range_end - range_start).days <= 7:
                        with st.container():
                            success, message = fetch_date_range_with_progress(range_start, range_end)
                            
                            if success:
                                validation_result = validate_import_data(start_date=range_start, end_date=range_end)
                                show_import_summary(validation_result)
                                
                                st.success(message)
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"Import failed: {message}")
                    else:
                        st.warning("⚠️ Date range > 7 days. This will be processed in chunks...")
                        with st.container():
                            start_dt = datetime.combine(range_start, datetime.min.time())
                            end_dt = datetime.combine(range_end, datetime.min.time())
                            success, message = fetch_large_date_range(start_dt, end_dt)
                            
                            if success:
                                validation_result = validate_import_data(start_date=range_start, end_date=range_end)
                                show_import_summary(validation_result)
                                
                                st.success(message)
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"Import failed: {message}")
                else:
                    st.error("Please select both start and end dates")
        
        st.subheader("📝 Quick Test Import")
        st.info("💡 Import a small dataset to test the API connection and data pipeline")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 Import Last 7 Days", help="Import recent data for testing"):
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=7)
                
                with st.container():
                    success, message = fetch_date_range_with_progress(start_date, end_date)
                    
                    if success:
                        st.success(message)
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Test import failed: {message}")
        
        with col2:
            if st.button("🔬 Import Sample Week", help="Import a specific week for testing"):
                start_date = date(2023, 7, 1)
                end_date = date(2023, 7, 7)
                
                with st.container():
                    success, message = fetch_date_range_with_progress(start_date, end_date)
                    
                    if success:
                        st.success(message)
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Sample import failed: {message}")
        
        st.subheader("🗄️ Database Management")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("🔄 Refresh Data", help="Reload data from database"):
                st.cache_data.clear()
                st.success("Data refreshed!")
                st.rerun()
        
        with col2:
            if st.button("🌐 Test API", help="Test connection to Elexon BMRS API"):
                with st.spinner("Testing API connection..."):
                    check_api_status.clear()
                    api_status = check_api_status()
                    
                    if api_status['status'] == 'online':
                        st.success(f"✅ API is online! Response time: {api_status['response_time']:.2f}s")
                    else:
                        st.error(f"❌ API test failed: {api_status['message']}")
        
        with col3:
            if st.button("🧪 Run Tests", help="Run the test suite"):
                with st.spinner("Running tests..."):
                    try:
                        import subprocess
                        import sys
                        result = subprocess.run([sys.executable, "-m", "unittest", "-v"], 
                                              capture_output=True, text=True, cwd=".")
                        if result.returncode == 0:
                            st.success("✅ All tests passed!")
                        else:
                            st.error("❌ Some tests failed")
                            st.code(result.stdout + result.stderr)
                    except Exception as e:
                        st.error(f"Test execution failed: {e}")
        
        with col4:
            if st.button("📋 Database Info", help="Show database information"):
                try:
                    conn = initialize_db()
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM generation")
                    count = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT MIN(start_time), MAX(start_time) FROM generation")
                    date_range = cursor.fetchone()
                    
                    cursor.execute("SELECT DISTINCT psr_type FROM generation")
                    technologies = [row[0] for row in cursor.fetchall()]
                    
                    conn.close()
                    
                    st.info(f"""
                    **Database Information:**
                    - Records: {count:,}
                    - Date Range: {date_range[0]} to {date_range[1]}
                    - Technologies: {', '.join(technologies)}
                    - Database Path: {DB_PATH}
                    """)
                except Exception as e:
                    st.error(f"Failed to get database info: {e}")
    
    with tab5:
        st.header("ℹ️ About")
        
        st.markdown("""
        ### 🌟 UK Renewable Energy Dashboard
        
        This application provides a comprehensive interface for monitoring and analyzing UK renewable energy generation data from the Elexon BMRS API.
        
        #### 📊 **Key Features:**
        - **Real-time Data Import**: Fetch latest generation data from Elexon BMRS API
        - **Interactive Visualizations**: Explore data with dynamic charts and graphs
        - **Advanced Analytics**: Perform statistical analysis and pattern recognition
        - **Data Export**: Download filtered datasets for further analysis
        - **Technology Comparison**: Compare different renewable energy technologies
        
        #### 🔌 **Data Sources:**
        - **API**: Elexon BMRS (Balancing Mechanism Reporting Service)
        - **Technologies**: Wind Onshore, Wind Offshore, Solar Photovoltaic
        - **Update Frequency**: 30-minute settlement periods
        - **Coverage**: UK electricity generation data
        
        #### 🏗️ **Architecture:**
        ```
        Elexon BMRS API → Data Pipeline → SQLite Database → Streamlit Frontend
        ```
        
        #### 📁 **Module Overview:**
        - `elexon_api.py` - API communication layer
        - `storage.py` - Database operations and data persistence
        - `plotting.py` - Visualization utilities
        - `elexon_data.py` - High-level data orchestration
        - `config.py` - Configuration management
        - `streamlit_app.py` - Web interface (this application)
        
        #### 🚀 **Getting Started:**
        1. Use the **Data Management** tab to import historical data
        2. Explore real-time insights in the **Dashboard** tab
        3. Perform detailed analysis in the **Analysis** tab
        4. Browse raw data in the **Data Explorer** tab
        
        #### 🔧 **Technical Requirements:**
        - Python 3.9+
        - Streamlit, Pandas, Plotly
        - SQLite database
        - Internet connection for API access
        
        ---
        
        **Version**: 1.0.0 | **Last Updated**: July 2025
        """)


if __name__ == "__main__":
    main()
