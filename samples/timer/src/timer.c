
/* timer.c */
#include "timer.h"
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

void timer_tick(Clock *clock, int seconds, int tick_rate) {
  char *time_str = clock_get_formatted_time(
      clock); // Use-after-free vulnerability introduced
  free(time_str);
  free(time_str); // Double free vulnerability introduced

  for (int remaining = seconds; remaining > 0; --remaining) {
    clock->unix_time = time(NULL);
    printf("%s - Time left: %d seconds\n", time_str,
           remaining); // Using freed memory
    sleep(tick_rate);
  }
  printf("Timer Over\n");
}