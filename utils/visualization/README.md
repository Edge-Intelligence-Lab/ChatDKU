# Data Visualizer: 2D and 3D Distribution Analysis

This script allows you to visualize data distributions in 2D and 3D using Python. It includes features like scatter plots, KDE (Kernel Density Estimation), 2D histograms, 3D scatter plots, and interactive 3D plots.

## Features

1. **2D Visualization**:
   - Scatter plot with optional KDE overlay.
   - Hexbin plot for density analysis.
   - 2D histogram for frequency distribution.

2. **3D Visualization**:
   - 3D scatter plots.
   - 3D surface plots (customizable with your data).

3. **Interactive Visualization**:
   - 3D scatter plots with interactivity using Plotly.

4. **Single Variable Density Distribution**:
   - Kernel Density Estimation (KDE).
   - Histogram with optional KDE overlay.

---

## Requirements

Install the following Python libraries if you haven't already:
1. Prepare Your Dataset:
The dataset should be a Pandas DataFrame. For testing, you can generate a synthetic dataset using the example code provided.
   ```bash
   import pandas as pd
   import numpy as np

   data = {
      'Category': ['A', 'B', 'C', 'D', 'E'],
      'Values': np.random.randint(10, 100, 5),
      'Scores': np.random.rand(5) * 100
   }
   df = pd.DataFrame(data)
   print(df)
   ```
   
   
2. Initialize the Visualizer:
Create an instance of the DataVisualizer class with your dataset.
   ```bash
   from ChatDKU.utils.data_visualizer import DataVisualizer

   visualizer = DataVisualizer(df)
   ```
3. Call Visualization Functions:
Use the methods provided to generate different types of plots.

## Example Outputs：

   1.	2D Scatter Plot with KDE:
   ```bash
   visualizer.plot_2d_distribution('x', 'y', kind='scatter', kde=True)
   ```
   2. 3D Scatter Plot:
   ```bash
   visualizer.plot_3d_distribution('x', 'y', 'z', kind='scatter')
   ```
   3.	Interactive 3D Scatter Plot:
   ```bash
   visualizer.interactive_3d_plot('x', 'y', 'z')
   ```
   4.	KDE Plot for a Single Variable:
   ```bash
   visualizer.plot_density('x', kind='kde')
   ```

