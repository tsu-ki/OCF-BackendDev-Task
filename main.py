"""
This script provides a command-line interface for:
- Fetching UK renewable generation data from Elexon BMRS API
- Storing data in SQLite database
- Visualizing generation trends
- Running data analysis

Usage:
    python main.py --help
    python main.py fetch-year 2023
    python main.py plot --start 2023-01-01 --end 2023-12-31
    python main.py analyze
    python main.py test
"""

import argparse
import sys
from datetime import datetime, timedelta
from typing import Optional

from ocf_pipeline import elexon_data as ed
from ocf_pipeline.storage import initialize_db, load_dataframe
from ocf_pipeline.plotting import plot_generation
import ocf_pipeline.elexon_api as api


def fetch_year_command(year: int) -> None:
    """Fetch a full year of generation data."""
    print(f"🔄 Fetching renewable generation data for {year}...")
    print("⚠️  This may take several minutes due to API rate limits.")
    
    try:
        ed.fetch_year(year)
        print(f"✅ Successfully imported {year} generation data to database.")
    except Exception as e:
        print(f"❌ Error fetching data for {year}: {e}")
        sys.exit(1)


def fetch_range_command(start_date: str, end_date: str) -> None:
    """Fetch data for a specific date range."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        if (end - start).days > 6:
            print("⚠️  Date range > 7 days. Chunking requests...")
            conn = initialize_db()
            current = start
            while current <= end:
                chunk_end = min(current + timedelta(days=6), end)
                print(f"📡 Fetching {current.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}")
                data = api.fetch_generation_data(current, chunk_end)
                if data:
                    from ocf_pipeline.storage import store_records
                    store_records(conn, data)
                current = chunk_end + timedelta(days=1)
            conn.close()
        else:
            print(f"📡 Fetching data from {start_date} to {end_date}...")
            data = api.fetch_generation_data(start, end)
            if data:
                conn = initialize_db()
                from ocf_pipeline.storage import store_records
                store_records(conn, data)
                conn.close()
                print(f"✅ Successfully imported {len(data)} records.")
            else:
                print("⚠️  No data returned from API.")
                
    except ValueError as e:
        print(f"❌ Invalid date format. Use YYYY-MM-DD: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        sys.exit(1)


def plot_command(start: Optional[str] = None, end: Optional[str] = None, psr_type: Optional[str] = None) -> None:
    """Generate plots of generation data."""
    try:
        conn = initialize_db()
        df = load_dataframe(conn, start=start, end=end, psr_type=psr_type)
        conn.close()
        
        if df.empty:
            print("⚠️  No data found in database for the specified criteria.")
            print("💡 Try running: python main.py fetch-year <year> first")
            return
            
        print(f"📊 Plotting {len(df)} data points...")
        if start or end:
            print(f"📅 Date range: {start or 'earliest'} to {end or 'latest'}")
        if psr_type:
            print(f"🔋 Technology: {psr_type}")
            
        plot_generation(df)
        
    except Exception as e:
        print(f"❌ Error generating plot: {e}")
        sys.exit(1)


def analyze_command() -> None:
    """Perform basic data analysis."""
    try:
        conn = initialize_db()
        df = load_dataframe(conn)
        conn.close()
        
        if df.empty:
            print("⚠️  No data found in database.")
            print("💡 Try running: python main.py fetch-year <year> first")
            return
        
        print("📈 ELEXON GENERATION DATA ANALYSIS")
        print("=" * 50)
        print(f"📊 Total records: {len(df):,}")
        print(f"📅 Date range: {df['start_time'].min()} to {df['start_time'].max()}")
        print()
        
        print("🔋 TECHNOLOGY BREAKDOWN:")
        tech_summary = df.groupby('psr_type').agg({
            'quantity': ['count', 'mean', 'max', 'sum']
        }).round(2)
        tech_summary.columns = ['Records', 'Avg MW', 'Peak MW', 'Total MWh']
        print(tech_summary)
        print()
        
        print("📊 DAILY AVERAGES BY TECHNOLOGY:")
        daily_avg = df.groupby(['start_time', 'psr_type'])['quantity'].mean().unstack(fill_value=0)
        print(daily_avg.describe().round(2))
        print()
        
        print("🏆 PEAK GENERATION RECORDS:")
        peak_records = df.loc[df.groupby('psr_type')['quantity'].idxmax()]
        for _, record in peak_records.iterrows():
            print(f"  {record['psr_type']}: {record['quantity']:.1f} MW on {record['start_time']}")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        sys.exit(1)


def test_command() -> None:
    """Run the test suite."""
    print("🧪 Running test suite...")
    import subprocess
    result = subprocess.run([sys.executable, "-m", "unittest", "-v"], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.returncode != 0:
        print("❌ Tests failed!")
        sys.exit(1)
    else:
        print("✅ All tests passed!")


def status_command() -> None:
    """Show database status and recent data."""
    try:
        conn = initialize_db()
        df = load_dataframe(conn)
        conn.close()
        
        print("🗄️  DATABASE STATUS")
        print("=" * 30)
        
        if df.empty:
            print("📭 Database is empty")
            print("💡 Run 'python main.py fetch-year <year>' to import data")
            return
        
        print(f"📊 Total records: {len(df):,}")
        print(f"📅 Date range: {df['start_time'].min().strftime('%Y-%m-%d')} to {df['start_time'].max().strftime('%Y-%m-%d')}")
        print(f"🔋 Technologies: {', '.join(df['psr_type'].unique())}")
        print()
        
        print("📈 RECENT DATA (Last 10 records):")
        recent = df.tail(10)[['start_time', 'psr_type', 'quantity']]
        for _, row in recent.iterrows():
            print(f"  {row['start_time']} | {row['psr_type']:<15} | {row['quantity']:>8.1f} MW")
            
    except Exception as e:
        print(f"❌ Error checking status: {e}")
        sys.exit(1)


def main():
    """Main entry point with command-line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Elexon Wind & Solar Generation Data Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py fetch-year 2023              # Import full year of data
  python main.py fetch-range 2023-01-01 2023-01-07  # Import specific date range
  python main.py plot                         # Plot all available data
  python main.py plot --start 2023-06-01     # Plot from specific date
  python main.py plot --psr-type "Wind Onshore"  # Plot specific technology
  python main.py analyze                      # Perform data analysis
  python main.py status                       # Show database status
  python main.py test                         # Run test suite
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Fetch year command
    fetch_year_parser = subparsers.add_parser('fetch-year', help='Fetch a full year of data')
    fetch_year_parser.add_argument('year', type=int, help='Year to fetch (e.g., 2023)')
    
    # Fetch range command
    fetch_range_parser = subparsers.add_parser('fetch-range', help='Fetch data for a specific date range')
    fetch_range_parser.add_argument('start_date', help='Start date (YYYY-MM-DD)')
    fetch_range_parser.add_argument('end_date', help='End date (YYYY-MM-DD)')
    
    # Plot command
    plot_parser = subparsers.add_parser('plot', help='Generate plots of generation data')
    plot_parser.add_argument('--start', help='Start date for plotting (YYYY-MM-DD)')
    plot_parser.add_argument('--end', help='End date for plotting (YYYY-MM-DD)')
    plot_parser.add_argument('--psr-type', help='Filter by PSR type (e.g., "Wind Onshore")')
    
    # Analysis command
    subparsers.add_parser('analyze', help='Perform data analysis')
    
    # Status command
    subparsers.add_parser('status', help='Show database status')
    
    # Test command
    subparsers.add_parser('test', help='Run the test suite')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    print("🌟 Elexon Wind & Solar Generation Pipeline")
    print("=" * 50)
    
    if args.command == 'fetch-year':
        fetch_year_command(args.year)
    elif args.command == 'fetch-range':
        fetch_range_command(args.start_date, args.end_date)
    elif args.command == 'plot':
        plot_command(args.start, args.end, args.psr_type)
    elif args.command == 'analyze':
        analyze_command()
    elif args.command == 'status':
        status_command()
    elif args.command == 'test':
        test_command()


if __name__ == "__main__":
    main()
