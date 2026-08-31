idf_component_register(SRCS "main.c" "bench_mac.c" "bench_encoder.c" "protocol.c" "link.c"
                            "timing.c" "tasks.c" "control.c"
                       INCLUDE_DIRS ".")

# Build-time switches, so that a variant is a rebuild rather than an edit and
# the firmware the paper reports is the firmware that was measured.
#
#   ./scripts/idf.sh -DFAULT_INJECT=1 build     scheduled fault injection
#   ./scripts/idf.sh -DFALLBACK_ENABLED=0 build ablation A4, handling off
#   ./scripts/idf.sh -DCTRL_PIPELINED=0 build   the synchronous loop
foreach(opt FAULT_INJECT FALLBACK_ENABLED CTRL_PIPELINED)
    if(DEFINED ${opt})
        target_compile_definitions(${COMPONENT_LIB} PRIVATE ${opt}=${${opt}})
        message(STATUS "evpil: ${opt}=${${opt}}")
    endif()
endforeach()
