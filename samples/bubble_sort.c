#include <stdio.h>

void buggy_bubble_sort(int arr[], int n) {
  for (int i = 0; i < n; i++) {
    for (int j = 0; j < n; j++) {
      // Out of bounds: j+1 when j == n-1
      if (arr[j] > arr[j + 1]) {
        int temp = arr[j];
        arr[j] = arr[j + 1];
        arr[j + 1] = temp;
      }
    }
  }
}

int main() {
  int arr[] = {5, 3, 2, 4, 1};
  int n = sizeof(arr) / sizeof(arr[0]);
  buggy_bubble_sort(arr, n);
  for (int i = 0; i < n; i++)
    printf("%d ", arr[i]);
  return 0;
}
