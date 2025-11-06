#include <limits.h>
#include <stdio.h>

#define V 5 // Number of vertices in graph

// Function to find the vertex with minimum distance value, from
// the set of vertices not yet included in shortest path tree
int minDistance(int dist[V], int sptSet[V]) {
  int min = INT_MAX, min_index = -1;
  for (int v = 0; v < V; v++)
    if (!sptSet[v] && dist[v] <= min) {
      min = dist[v];
      min_index = v;
    }
  return min_index;
}

// Function to print shortest distances from source to all vertices
void printSolution(int dist[V]) {
  printf("Vertex \t Distance from Source\n");
  for (int i = 0; i < V; i++)
    printf("%d \t\t %d\n", i, dist[i]);
}

// Implements Dijkstra's algorithm for a graph represented using adjacency
// matrix
void dijkstra(int graph[V][V], int src) {
  int dist[V];   // Output array, dist[i] holds shortest distance from src to i
  int sptSet[V]; // sptSet[i] true if vertex i included in shortest path tree

  // Initialize all distances as infinite and sptSet[] as false
  for (int i = 0; i < V; i++) {
    dist[i] = INT_MAX;
    sptSet[i] = 0;
  }

  dist[src] = 0; // Distance of source vertex from itself is always 0

  // Find shortest path for all vertices
  for (int count = 0; count < V - 1; count++) {
    int u = minDistance(dist, sptSet);
    sptSet[u] = 1; // Mark vertex u as processed

    // Update dist value of the adjacent vertices of the picked vertex
    for (int v = 0; v < V; v++)
      if (!sptSet[v] && graph[u][v] && dist[u] != INT_MAX &&
          dist[u] + graph[u][v] < dist[v])
        dist[v] = dist[u] + graph[u][v];
  }

  printSolution(dist);
}

int main() {
  // Example graph (adjacency matrix) - 5 vertices
  int graph[V][V] = {
      {0, 10, 0, 30, 100}, {10, 0, 50, 0, 0},   {0, 50, 0, 20, 10},
      {30, 0, 20, 0, 60},  {100, 0, 10, 60, 0},
  };

  dijkstra(graph, 0); // Compute shortest paths from vertex 0

  return 0;
}
