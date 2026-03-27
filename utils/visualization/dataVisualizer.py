import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from mpl_toolkits.mplot3d import Axes3D
import plotly.express as px

class DataVisualizer:
    def __init__(self, data):
        """
        Initialize with data.
        :param data: A Pandas DataFrame containing the dataset.
        """
        self.data = data

    def plot_2d_distribution(self, x_col, y_col, kind='scatter', bins=30, kde=True, cmap='viridis'):
        """
        Visualize 2D data distribution.
        :param x_col: Column name for the x-axis.
        :param y_col: Column name for the y-axis.
        :param kind: Type of plot ('scatter', 'hexbin', or 'hist2d').
        :param bins: Number of bins for hexbin or hist2d.
        :param kde: Whether to include KDE in scatter plots.
        :param cmap: Colormap for hexbin and hist2d.
        """
        if kind == 'scatter':
            plt.figure(figsize=(8, 6))
            sns.scatterplot(data=self.data, x=x_col, y=y_col)
            if kde:
                sns.kdeplot(data=self.data, x=x_col, y=y_col, levels=5, color='red', alpha=0.6)
            plt.title(f"2D Scatter Plot of {x_col} vs {y_col}")
            plt.show()
        elif kind == 'hexbin':
            plt.figure(figsize=(8, 6))
            plt.hexbin(self.data[x_col], self.data[y_col], gridsize=bins, cmap=cmap)
            plt.colorbar(label='Frequency')
            plt.title(f"Hexbin Plot of {x_col} vs {y_col}")
            plt.xlabel(x_col)
            plt.ylabel(y_col)
            plt.show()
        elif kind == 'hist2d':
            plt.figure(figsize=(8, 6))
            plt.hist2d(self.data[x_col], self.data[y_col], bins=bins, cmap=cmap)
            plt.colorbar(label='Frequency')
            plt.title(f"2D Histogram of {x_col} vs {y_col}")
            plt.xlabel(x_col)
            plt.ylabel(y_col)
            plt.show()
        else:
            print("Unsupported plot kind. Choose 'scatter', 'hexbin', or 'hist2d'.")

    def plot_3d_distribution(self, x_col, y_col, z_col, kind='scatter', cmap='viridis'):
        """
        Visualize 3D data distribution.
        :param x_col: Column name for the x-axis.
        :param y_col: Column name for the y-axis.
        :param z_col: Column name for the z-axis.
        :param kind: Type of plot ('scatter' or 'surface').
        :param cmap: Colormap for surface plot.
        """
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')

        if kind == 'scatter':
            ax.scatter(self.data[x_col], self.data[y_col], self.data[z_col], c=self.data[z_col], cmap=cmap)
            ax.set_title(f"3D Scatter Plot of {x_col}, {y_col}, and {z_col}")
        elif kind == 'surface':
            # Create grid
            X, Y = np.meshgrid(
                np.linspace(self.data[x_col].min(), self.data[x_col].max(), 30),
                np.linspace(self.data[y_col].min(), self.data[y_col].max(), 30)
            )
            Z = np.sin(X) * np.cos(Y)  # Example; replace with your own data interpolation logic
            ax.plot_surface(X, Y, Z, cmap=cmap, edgecolor='k', alpha=0.7)
            ax.set_title(f"3D Surface Plot of {x_col}, {y_col}, and {z_col}")
        else:
            print("Unsupported plot kind. Choose 'scatter' or 'surface'.")

        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        ax.set_zlabel(z_col)
        plt.show()

    def interactive_3d_plot(self, x_col, y_col, z_col):
        """
        Create an interactive 3D scatter plot.
        :param x_col: Column name for the x-axis.
        :param y_col: Column name for the y-axis.
        :param z_col: Column name for the z-axis.
        """
        fig = px.scatter_3d(self.data, x=x_col, y=y_col, z=z_col, color=z_col, title="Interactive 3D Plot")
        fig.show()

    def plot_density(self, col, kind='kde', bins=30, color='blue'):
        """
        Plot density distribution of a single variable.
        :param col: Column name for the variable.
        :param kind: Type of plot ('kde' or 'hist').
        :param bins: Number of bins for histograms.
        :param color: Color of the plot.
        """
        plt.figure(figsize=(8, 6))
        if kind == 'kde':
            sns.kdeplot(self.data[col], color=color, fill=True, alpha=0.5)
            plt.title(f"Kernel Density Plot of {col}")
        elif kind == 'hist':
            sns.histplot(self.data[col], bins=bins, color=color, kde=True)
            plt.title(f"Histogram of {col}")
        else:
            print("Unsupported plot kind. Choose 'kde' or 'hist'.")
        plt.xlabel(col)
        plt.ylabel('Density')
        plt.show()

# Example usage
if __name__ == '__main__':
    # Generate sample data
    np.random.seed(42)
    data = pd.DataFrame({
        'x': np.random.normal(size=500),
        'y': np.random.normal(size=500),
        'z': np.random.normal(size=500)
    })

    visualizer = DataVisualizer(data)
    visualizer.plot_2d_distribution('x', 'y', kind='scatter', kde=True)
    visualizer.plot_3d_distribution('x', 'y', 'z', kind='scatter')
    visualizer.interactive_3d_plot('x', 'y', 'z')
    visualizer.plot_density('x', kind='kde')