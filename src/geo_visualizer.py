import matplotlib.pyplot as plt
import os

def generate_regional_density_map(final_precincts_gdf, output_dir="data/geo/"):
    """Generates the 2x2 regional comparison map."""
    regions = {
        "St. Louis Area": ['189', '510'],
        "Kansas City Area (Jackson)": ['095'],
        "Columbia Area (Boone)": ['019'],
        "Dade County (Resource Desert)": ['057']
    }

    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    fig.suptitle("Geographic Resource Strain: Urban vs. Rural Contrast", fontsize=24, fontweight='bold', y=0.95)
    axes = axes.flatten()

    for i, (title, fips_list) in enumerate(regions.items()):
        ax = axes[i]
        region_gdf = final_precincts_gdf[final_precincts_gdf['COUNTYFP20'].isin(fips_list)]
        
        region_gdf.plot(
            column='Sq_Miles_Per_Poll',
            ax=ax, cmap='OrRd', linewidth=0.5, edgecolor='black', legend=True, vmin=0,
            legend_kwds={'shrink': 0.7, 'label': 'Sq Miles per Poll'},
            missing_kwds={"color": "none", "edgecolor": "black", "linewidth": 0.5}
        )
        ax.set_title(title, fontsize=18, pad=10)
        ax.axis('off')

    plt.tight_layout(rect=[0, 0.03, 1, 0.92])
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, "MO_Regional_Coverage_Zoom.png"), dpi=300, bbox_inches='tight', facecolor='white')
    plt.close() # Close plot to free up memory

def generate_commute_bar_chart(final_precincts_gdf, output_dir="data/geo/"):
    """Generates the horizontal bar chart for transportation barriers."""
    # Group math to county level
    summary = final_precincts_gdf.groupby('COUNTYFP20').agg(
        Total_Area=('Area_Sq_Miles', 'sum'),
        Total_Polls=('Polling_Locations_Count', 'sum')
    ).reset_index()
    summary['Coverage_Area'] = summary['Total_Area'] / summary['Total_Polls']

    fips_map = {'189': 'St. Louis County', '095': 'Jackson County', '019': 'Boone County', '057': 'Dade County'}
    chart_df = summary[summary['COUNTYFP20'].isin(fips_map.keys())].copy()
    chart_df['County_Name'] = chart_df['COUNTYFP20'].map(fips_map)
    chart_df = chart_df.sort_values('Coverage_Area', ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(chart_df['County_Name'], chart_df['Coverage_Area'], color=['#d3d3d3', '#a9a9a9', '#ff7b7b', '#a70000'], edgecolor='black')
    
    ax.set_title("Average Square Miles Assigned to a Single Polling Place", fontsize=18, pad=20)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    for bar in bars:
        width = bar.get_width()
        ax.text(width + 2, bar.get_y() + bar.get_height()/2, f'{width:.1f} sq mi', va='center', fontsize=12)

    plt.tight_layout()
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, "MO_Transportation_Barrier_Chart.png"), dpi=300, facecolor='white')
    plt.close()