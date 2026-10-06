set(EVPIL_SRCS "main.c" "bench_mac.c" "bench_encoder.c" "protocol.c" "link.c"
               "timing.c" "tasks.c" "control.c")

# The actor's weights are generated from a trained policy by
# scripts/verify_actor.py --export. Compiling the inference code only when
# that header exists keeps the firmware buildable in a checkout where no
# policy has been trained yet, and makes the absence explicit rather than a
# missing-include error twenty lines into a build log.
if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/sac_actor_weights.h")
    list(APPEND EVPIL_SRCS "actor.c" "bench_actor.c")
    message(STATUS "evpil: SAC actor weights found, actor inference included")
else()
    message(STATUS "evpil: no sac_actor_weights.h; actor inference omitted. "
                   "Run scripts/verify_actor.py --export to generate it")
endif()

idf_component_register(SRCS ${EVPIL_SRCS} INCLUDE_DIRS ".")

if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/sac_actor_weights.h")
    target_compile_definitions(${COMPONENT_LIB} PRIVATE HAVE_SAC_ACTOR=1)
endif()

# Build-time switches, so that a variant is a rebuild rather than an edit and
# the firmware the paper reports is the firmware that was measured.
#
#   ./scripts/idf.sh -DFAULT_INJECT=1 build     scheduled fault injection
#   ./scripts/idf.sh -DFALLBACK_ENABLED=0 build ablation A4, handling off
#   ./scripts/idf.sh -DCTRL_PIPELINED=0 build   the synchronous loop
#   ./scripts/idf.sh -DRUN_ACTOR_BENCH=1 build  verify and time the actor
#   ./scripts/idf.sh -DRUN_G1_BENCHMARK=1 build gate G1, int8 MAC throughput
#   ./scripts/idf.sh -DRUN_G5_BENCHMARK=1 build gate G5, encoder latency
#   ./scripts/idf.sh -DSPEED_FILTER_ALPHA=0.30f build  fixed speed filter
foreach(opt FAULT_INJECT FALLBACK_ENABLED CTRL_PIPELINED RUN_ACTOR_BENCH
            RUN_G1_BENCHMARK RUN_G5_BENCHMARK SPEED_FILTER_ALPHA)
    if(DEFINED ${opt})
        target_compile_definitions(${COMPONENT_LIB} PRIVATE ${opt}=${${opt}})
        message(STATUS "evpil: ${opt}=${${opt}}")
    endif()
endforeach()
