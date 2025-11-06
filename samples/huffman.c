#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_TREE_HT 100

// A Huffman tree node
struct MinHeapNode {
  char data;     // One character
  unsigned freq; // Frequency of the character
  struct MinHeapNode *left, *right;
};

// Min heap: collection of min heap nodes
struct MinHeap {
  unsigned size;     // Current size of min heap
  unsigned capacity; // capacity
  struct MinHeapNode **array;
};

// Create a new min heap node
struct MinHeapNode *newNode(char data, unsigned freq) {
  struct MinHeapNode *temp =
      (struct MinHeapNode *)malloc(sizeof(struct MinHeapNode));
  temp->left = temp->right = NULL;
  temp->data = data;
  temp->freq = freq;
  return temp;
}

// Create a min heap of given capacity
struct MinHeap *createMinHeap(unsigned capacity) {
  struct MinHeap *minHeap = (struct MinHeap *)malloc(sizeof(struct MinHeap));
  minHeap->size = 0;
  minHeap->capacity = capacity;
  minHeap->array = (struct MinHeapNode **)malloc(minHeap->capacity *
                                                 sizeof(struct MinHeapNode *));
  return minHeap;
}

// Swap two min heap nodes
void swapMinHeapNode(struct MinHeapNode **a, struct MinHeapNode **b) {
  struct MinHeapNode *t = *a;
  *a = *b;
  *b = t;
}

// Heapify at given idx
void minHeapify(struct MinHeap *minHeap, int idx) {
  int smallest = idx;
  int left = 2 * idx + 1;
  int right = 2 * idx + 2;
  if (left < minHeap->size &&
      minHeap->array[left]->freq < minHeap->array[smallest]->freq)
    smallest = left;
  if (right < minHeap->size &&
      minHeap->array[right]->freq < minHeap->array[smallest]->freq)
    smallest = right;
  if (smallest != idx) {
    swapMinHeapNode(&minHeap->array[smallest], &minHeap->array[idx]);
    minHeapify(minHeap, smallest);
  }
}

// Check if size is 1
int isSizeOne(struct MinHeap *minHeap) { return (minHeap->size == 1); }

// Extract min node
struct MinHeapNode *extractMin(struct MinHeap *minHeap) {
  struct MinHeapNode *temp = minHeap->array[0];
  minHeap->array[0] = minHeap->array[minHeap->size - 1];
  --minHeap->size;
  minHeapify(minHeap, 0);
  return temp;
}

// Insert a new node to min heap
void insertMinHeap(struct MinHeap *minHeap, struct MinHeapNode *minHeapNode) {
  ++minHeap->size;
  int i = minHeap->size - 1;
  while (i && minHeapNode->freq < minHeap->array[(i - 1) / 2]->freq) {
    minHeap->array[i] = minHeap->array[(i - 1) / 2];
    i = (i - 1) / 2;
  }
  minHeap->array[i] = minHeapNode;
}

// Build min heap
void buildMinHeap(struct MinHeap *minHeap) {
  int n = minHeap->size - 1;
  for (int i = (n - 1) / 2; i >= 0; --i)
    minHeapify(minHeap, i);
}

// Check if leaf node
int isLeaf(struct MinHeapNode *root) { return !(root->left) && !(root->right); }

// Create min heap and inserts all characters of data[]
struct MinHeap *createAndBuildMinHeap(char data[], int freq[], int size) {
  struct MinHeap *minHeap = createMinHeap(size);
  for (int i = 0; i < size; ++i)
    minHeap->array[i] = newNode(data[i], freq[i]);
  minHeap->size = size;
  buildMinHeap(minHeap);
  return minHeap;
}

// Build Huffman tree
struct MinHeapNode *buildHuffmanTree(char data[], int freq[], int size) {
  struct MinHeapNode *left, *right, *top;
  struct MinHeap *minHeap = createAndBuildMinHeap(data, freq, size);
  while (!isSizeOne(minHeap)) {
    left = extractMin(minHeap);
    right = extractMin(minHeap);
    top = newNode('$', left->freq + right->freq);
    top->left = left;
    top->right = right;
    insertMinHeap(minHeap, top);
  }
  return extractMin(minHeap);
}

// Print codes from root of Huffman tree
void printCodes(struct MinHeapNode *root, int arr[], int top) {
  // Assign 0 to left edge
  if (root->left) {
    arr[top] = 0;
    printCodes(root->left, arr, top + 1);
  }
  // Assign 1 to right edge
  if (root->right) {
    arr[top] = 1;
    printCodes(root->right, arr, top + 1);
  }
  // If leaf node, print code
  if (isLeaf(root)) {
    printf("%c: ", root->data);
    for (int i = 0; i < top; ++i)
      printf("%d", arr[i]);
    printf("\n");
  }
}

// Huffman coding main function
void HuffmanCodes(char data[], int freq[], int size) {
  struct MinHeapNode *root = buildHuffmanTree(data, freq, size);
  int arr[MAX_TREE_HT], top = 0;
  printCodes(root, arr, top);
}

// Example run in main()
int main() {
  // Example 1
  char arr1[] = {'a', 'b', 'c', 'd', 'e', 'f'};
  int freq1[] = {5, 9, 12, 13, 16, 45};
  int size1 = sizeof(arr1) / sizeof(arr1[0]);

  printf("Example 1 Huffman Codes:\n");
  HuffmanCodes(arr1, freq1, size1);
  printf("\n");

  // Example 2
  char arr2[] = {'x', 'y', 'z'};
  int freq2[] = {1, 1, 2};
  int size2 = sizeof(arr2) / sizeof(arr2[0]);

  printf("Example 2 Huffman Codes:\n");
  HuffmanCodes(arr2, freq2, size2);

  return 0;
}
