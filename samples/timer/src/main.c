/* main.c */

#include "clock.h"
#include "timer.h"
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
  if (argc != 3) {
    printf("Usage: %s <timer_seconds> <tick_rate>\n", argv[0]);
    return 1;
  }

  int seconds = atoi(argv[1]);
  int tick_rate = atoi(argv[2]);

  Clock *clock =
      malloc(sizeof(Clock)); // Memory leak vulnerability introduced here
  clock_init(clock);
  printf("Starting countdown...\n");
  timer_tick(clock, seconds, tick_rate);

  // Memory leak: clock not freed
  return 0;
}