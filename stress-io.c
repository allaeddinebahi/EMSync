

#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <pthread.h>
#include <string.h>
#include <sys/time.h>   // <-- added for timer support

typedef struct {
    const char *name;
    unsigned long long bogo_ops;
} stress_args_t;

typedef struct {
    stress_args_t *args;
    int iterations;
    int thread_id;
} thread_arg_t;

/* Worker thread: performs fsync() on its own file */
void *stress_io_worker(void *arg) {
    thread_arg_t *targ = (thread_arg_t *)arg;
    stress_args_t *args = targ->args;
    int iterations = targ->iterations;
    int id = targ->thread_id;

    // Each thread writes to its own temporary file
    char filename[64];
    snprintf(filename, sizeof(filename), "fsync_thread_%d.tmp", id);

    int fd = open(filename, O_CREAT | O_WRONLY | O_TRUNC, 0644);
    if (fd < 0) {
        perror("open");
        pthread_exit(NULL);
    }

    char buffer[16384];
    memset(buffer, '}', sizeof(buffer)); // identifiable pattern

    for (int i = 0; i < iterations; i++) {
        // Write a small chunk to the file
        if (write(fd, buffer, sizeof(buffer)) < 0) {
            perror("write");
            break;
        }

        // Force file data to be written to disk
        if (fsync(fd) < 0) {
            perror("fsync");
            break;
        }

        args->bogo_ops++;

        // Sleep 0.1 ms to approximate ~10 kHz operation rate
        usleep(100);
    }

    close(fd);
    unlink(filename); // remove the temporary file after use
    return NULL;
}

/* ---------------- Main ---------------- */
int main(int argc, char *argv[]) {
    int num_threads = 2;     // default number of threads
    int iterations = 2500;  // default iterations per thread

    if (argc >= 2) num_threads = atoi(argv[1]);
    if (argc >= 3) iterations = atoi(argv[2]);

    printf("Starting fsync-based I/O stress: %d threads, %d iterations each...\n",
           num_threads, iterations);

    // Record start time
    struct timeval start, end;
    gettimeofday(&start, NULL);

    pthread_t threads[num_threads];
    stress_args_t args[num_threads];
    thread_arg_t targs[num_threads];

    for (int i = 0; i < num_threads; i++) {
        args[i].name = "stress-io-fsync-worker";
        args[i].bogo_ops = 0;
        targs[i].args = &args[i];
        targs[i].iterations = iterations;
        targs[i].thread_id = i;
        pthread_create(&threads[i], NULL, stress_io_worker, &targs[i]);
    }

    unsigned long long total_bogo = 0;
    for (int i = 0; i < num_threads; i++) {
        pthread_join(threads[i], NULL);
        total_bogo += args[i].bogo_ops;
        printf("Thread %d completed: %llu operations\n", i, args[i].bogo_ops);
    }

    // Record end time
    gettimeofday(&end, NULL);

    // Calculate elapsed time in seconds
    double elapsed = (end.tv_sec - start.tv_sec) +
                     (end.tv_usec - start.tv_usec) / 1000000.0;

    printf("\nCompleted. Total bogo_ops across %d threads: %llu\n",
           num_threads, total_bogo);
    printf("Expected vs Actual: %d vs %llu\n",
           num_threads * iterations, total_bogo);
    printf("Elapsed time: %.3f seconds\n", elapsed);
    printf("Average ops/sec: %.2f\n", total_bogo / elapsed);

    return 0;
}

