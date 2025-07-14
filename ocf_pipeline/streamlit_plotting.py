"""
Provides interactive visualizations using Plotly for better web integration.
"""

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Optional, Tuple, List
from datetime import datetime, timedelta


def create_enhanced_time_series(df: pd.DataFrame, 
                               title: str = "Generation Over Time",
                               height: int = 500) -> go.Figure:
    """Create time series plot with multiple series and annotations."""
    if df.empty:
        return None
    
    fig = go.Figure()
    
    for tech in df['psr_type'].unique():
        tech_data = df[df['psr_type'] == tech]
        fig.add_trace(go.Scatter(
            x=tech_data['start_time'],
            y=tech_data['quantity'],
            mode='lines',
            name=tech,
            line=dict(width=2),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                         'Time: %{x}<br>' +
                         'Generation: %{y:.1f} MW<br>' +
                         '<extra></extra>'
        ))
    
    if len(df) > 24:
        for tech in df['psr_type'].unique():
            tech_data = df[df['psr_type'] == tech].sort_values('start_time')
            if len(tech_data) > 10:
                tech_data['ma_24'] = tech_data['quantity'].rolling(window=24, center=True).mean()
                fig.add_trace(go.Scatter(
                    x=tech_data['start_time'],
                    y=tech_data['ma_24'],
                    mode='lines',
                    name=f'{tech} (24h MA)',
                    line=dict(dash='dash', width=1),
                    opacity=0.7,
                    showlegend=False,
                    hovertemplate='<b>%{fullData.name}</b><br>' +
                                 'Time: %{x}<br>' +
                                 'MA Generation: %{y:.1f} MW<br>' +
                                 '<extra></extra>'
                ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title="Generation (MW)",
        height=height,
        hovermode='x unified',
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=1.01
        )
    )
    
    return fig


def create_generation_summary_chart(df: pd.DataFrame) -> go.Figure:
    """Create summary chart with multiple metrics."""
    if df.empty:
        return None
    
    # summary statistics
    summary = df.groupby('psr_type').agg({
        'quantity': ['mean', 'max', 'min', 'std', 'sum']
    }).round(2)
    summary.columns = ['Mean', 'Max', 'Min', 'Std Dev', 'Total']
    summary = summary.reset_index()
    
    # subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Average Generation', 'Peak Generation', 
                       'Total Generation Share', 'Generation Variability'),
        specs=[[{"type": "bar"}, {"type": "bar"}],
               [{"type": "pie"}, {"type": "bar"}]]
    )
    
    # Average generation
    fig.add_trace(
        go.Bar(x=summary['psr_type'], y=summary['Mean'], name='Avg MW',
               marker_color='lightblue', showlegend=False),
        row=1, col=1
    )
    
    # Peak generation
    fig.add_trace(
        go.Bar(x=summary['psr_type'], y=summary['Max'], name='Peak MW',
               marker_color='orange', showlegend=False),
        row=1, col=2
    )
    
    # Total generation pie chart
    fig.add_trace(
        go.Pie(labels=summary['psr_type'], values=summary['Total'], name="Share",
               showlegend=False),
        row=2, col=1
    )
    
    # Variability (coefficient of variation)
    cv = (summary['Std Dev'] / summary['Mean'] * 100).fillna(0)
    fig.add_trace(
        go.Bar(x=summary['psr_type'], y=cv, name='CV %',
               marker_color='green', showlegend=False),
        row=2, col=2
    )
    
    fig.update_layout(height=600, title_text="Generation Summary Dashboard")
    
    return fig


def create_capacity_factor_analysis(df: pd.DataFrame, 
                                   installed_capacity: Optional[dict] = None) -> go.Figure:
    """Create capacity factor analysis if installed capacity data is available."""
    if df.empty:
        return None
    
    # Default capacity estimates (MW) - approximate values
    default_capacity = {
        'Wind Onshore': 14000,
        'Wind Offshore': 8000,
        'Solar Photovoltaic': 13000
    }
    
    capacity_data = installed_capacity or default_capacity
    
    # capacity factors
    cf_data = []
    for tech in df['psr_type'].unique():
        if tech in capacity_data:
            tech_data = df[df['psr_type'] == tech]
            avg_generation = tech_data['quantity'].mean()
            capacity_factor = (avg_generation / capacity_data[tech]) * 100
            cf_data.append({
                'Technology': tech,
                'Capacity Factor (%)': capacity_factor,
                'Installed Capacity (MW)': capacity_data[tech],
                'Average Generation (MW)': avg_generation
            })
    
    if not cf_data:
        return None
    
    cf_df = pd.DataFrame(cf_data)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=cf_df['Technology'],
        y=cf_df['Capacity Factor (%)'],
        name='Capacity Factor',
        text=cf_df['Capacity Factor (%)'].round(1),
        textposition='auto',
        marker_color=['#1f77b4', '#ff7f0e', '#2ca02c']
    ))
    
    fig.update_layout(
        title='Capacity Factor Analysis',
        xaxis_title='Technology',
        yaxis_title='Capacity Factor (%)',
        height=400,
        showlegend=False
    )

    for i, row in cf_df.iterrows():
        fig.add_annotation(
            x=row['Technology'],
            y=row['Capacity Factor (%)'] + 1,
            text=f"Avg: {row['Average Generation (MW)']:.0f} MW",
            showarrow=False,
            font=dict(size=10)
        )
    
    return fig


def create_seasonal_heatmap(df: pd.DataFrame) -> go.Figure:
    """Create a seasonal heatmap showing generation patterns."""
    if df.empty:
        return None
    
    df_copy = df.copy()
    df_copy['month'] = df_copy['start_time'].dt.month
    df_copy['hour'] = df_copy['start_time'].dt.hour
    
    # heatmap data
    technologies = df_copy['psr_type'].unique()
    
    if len(technologies) == 1:
        # Single technology heatmap
        tech = technologies[0]
        heatmap_data = df_copy.pivot_table(
            index='hour', 
            columns='month', 
            values='quantity', 
            aggfunc='mean'
        ).fillna(0)
        
        fig = go.Figure(data=go.Heatmap(
            z=heatmap_data.values,
            x=[f'Month {i}' for i in range(1, 13)],
            y=[f'{i:02d}:00' for i in range(24)],
            colorscale='Viridis',
            hoverongaps=False
        ))
        
        fig.update_layout(
            title=f'Seasonal Generation Pattern - {tech}',
            xaxis_title='Month',
            yaxis_title='Hour of Day',
            height=500
        )
    
    else:
        # subplots for multiple technologies
        fig = make_subplots(
            rows=1, cols=len(technologies),
            subplot_titles=technologies,
            shared_yaxes=True
        )
        
        for i, tech in enumerate(technologies):
            tech_data = df_copy[df_copy['psr_type'] == tech]
            heatmap_data = tech_data.pivot_table(
                index='hour', 
                columns='month', 
                values='quantity', 
                aggfunc='mean'
            ).fillna(0)
            
            fig.add_trace(
                go.Heatmap(
                    z=heatmap_data.values,
                    x=[f'M{j}' for j in range(1, 13)],
                    y=[f'{j:02d}:00' for j in range(24)],
                    colorscale='Viridis',
                    showscale=(i == len(technologies) - 1),
                    hoverongaps=False
                ),
                row=1, col=i+1
            )
        
        fig.update_layout(
            title='Seasonal Generation Patterns by Technology',
            height=500
        )
    
    return fig


def create_correlation_matrix(df: pd.DataFrame) -> go.Figure:
    """Create correlation matrix between different technologies."""
    if df.empty or len(df['psr_type'].unique()) < 2:
        return None
    
    pivot_df = df.pivot_table(
        index='start_time',
        columns='psr_type',
        values='quantity',
        aggfunc='mean'
    ).fillna(0)
    
    # correlation matrix
    corr_matrix = pivot_df.corr()
    
    # heatmap
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=corr_matrix.columns,
        y=corr_matrix.columns,
        colorscale='RdBu',
        zmid=0,
        text=corr_matrix.round(3),
        texttemplate="%{text}",
        textfont={"size": 12},
        hoverongaps=False
    ))
    
    fig.update_layout(
        title='Technology Correlation Matrix',
        xaxis_title='Technology',
        yaxis_title='Technology',
        height=400,
        width=400
    )
    
    return fig


def create_distribution_plot(df: pd.DataFrame) -> go.Figure:
    """Create distribution plots for generation data."""
    if df.empty:
        return None
    
    fig = go.Figure()
    
    # histogram for each technology
    for i, tech in enumerate(df['psr_type'].unique()):
        tech_data = df[df['psr_type'] == tech]['quantity']
        
        fig.add_trace(go.Histogram(
            x=tech_data,
            name=tech,
            opacity=0.7,
            nbinsx=30,
            histnorm='probability density'
        ))
    
    fig.update_layout(
        title='Generation Distribution by Technology',
        xaxis_title='Generation (MW)',
        yaxis_title='Probability Density',
        height=400,
        barmode='overlay'
    )
    
    return fig


def create_weekly_pattern(df: pd.DataFrame) -> go.Figure:
    """Create weekly pattern analysis."""
    if df.empty:
        return None
    
    df_copy = df.copy()
    df_copy['day_of_week'] = df_copy['start_time'].dt.day_name()
    df_copy['hour'] = df_copy['start_time'].dt.hour
    
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    weekly_avg = df_copy.groupby(['day_of_week', 'psr_type'])['quantity'].mean().reset_index()
    
    fig = px.bar(weekly_avg, 
                x='day_of_week', 
                y='quantity', 
                color='psr_type',
                title='Average Generation by Day of Week',
                labels={'quantity': 'Average Generation (MW)', 'day_of_week': 'Day of Week'},
                category_orders={'day_of_week': day_order})
    
    fig.update_layout(height=400)
    
    return fig


def create_performance_metrics_table(df: pd.DataFrame) -> pd.DataFrame:
    """Create a comprehensive performance metrics table."""
    if df.empty:
        return pd.DataFrame()
    
    metrics = []
    
    for tech in df['psr_type'].unique():
        tech_data = df[df['psr_type'] == tech]['quantity']
        
        metrics.append({
            'Technology': tech,
            'Records': len(tech_data),
            'Mean (MW)': tech_data.mean(),
            'Median (MW)': tech_data.median(),
            'Std Dev (MW)': tech_data.std(),
            'Min (MW)': tech_data.min(),
            'Max (MW)': tech_data.max(),
            'P25 (MW)': tech_data.quantile(0.25),
            'P75 (MW)': tech_data.quantile(0.75),
            'CV (%)': (tech_data.std() / tech_data.mean() * 100) if tech_data.mean() > 0 else 0,
            'Total (MWh)': tech_data.sum()
        })
    
    metrics_df = pd.DataFrame(metrics)
    return metrics_df.round(2)
