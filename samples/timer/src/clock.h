/* clock.h */
#ifndef CLOCK_H
#define CLOCK_H

#include <time.h>

typedef struct {
  time_t unix_time;
} Clock;

void clock_init(Clock *clock);
char *clock_get_formatted_time(Clock *clock);

#endif // CLOCK_H