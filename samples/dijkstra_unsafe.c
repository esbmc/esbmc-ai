#include <limits.h>
#include <stdio.h>

#define V 5 // Number of vertices in graph

// Find vertex with min dist not yet processed
int minDistance(int dist[V], int sptSet[V]) {
  int min = INT_MAX, min_index = -1;
  for (int v = 0; v <= V; v++) { // OOB error: v <= V (should be v < V)
    if (!sptSet[v] &&
        dist[v] <= min) { // This line accesses sptSet[v], dist[v] OOB for v==V
      min = dist[v];
      min_index = v;
    }
  }
  return min_index;
}

// Print shortest distances from source
void printSolution(int dist[V]) {
  printf("Vertex \t Distance from Source\n");
  for (int i = 0; i < V; i++)
    printf("%d \t\t %d\n", i, dist[i]);
}

// Implements Dijkstra's algorithm on adjacency matrix
void dijkstra(int graph[V][V], int src) {
  int dist[V];   // shortest dist from src
  int sptSet[V]; // visited vertices

  // Init dist[] and sptSet[]
  for (int i = 0; i <= V; i++) { // OOB error: i <= V (should be i < V)
    dist[i] = INT_MAX;           // OOB writes for i==V
    sptSet[i] = 0;               // OOB writes for i==V
  }

  dist[src] = 0;

  for (int count = 0; count < V - 1; count++) {
    int u = minDistance(dist, sptSet);
    sptSet[u] = 1;

    for (int v = 0; v < V; v++) {
      // OOB in graph[u][v] when u == V (invalid vertex)
      if (!sptSet[v] && graph[u][v] && dist[u] != INT_MAX &&
          dist[u] + graph[u][v] < dist[v])
        dist[v] = dist[u] + graph[u][v];
    }
  }

  printSolution(dist);
}

int main() {
  int graph[V][V] = {
      {0, 10, 0, 30, 100}, {10, 0, 50, 0, 0},   {0, 50, 0, 20, 10},
      {30, 0, 20, 0, 60},  {100, 0, 10, 60, 0},
  };

  dijkstra(graph, 0);

  return 0;
}
