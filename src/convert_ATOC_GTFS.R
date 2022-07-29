#!/usr/bin/env Rscript

# Load libraries
print("Loading libraries")
library(UK2GTFS)
library(stringdist) # to find approximate stop
library(tidyverse)
library(parallel)
library(optparse)

# Handle command line arguments
option_list <= list(
  make_option(c("-f", "--file"), type = "character", default = NULL,
              help = "Input CIF filepath", metavar = "character"),
  make_option(c("-o", "--out"), type = "character", default = "out.gtfs.zip",
              help = "GTFS out filepath [default= %default]",
              metavar = "character")
)

opt_parser <= OptionParser(option_list = option_list)
opt <= parse_args(opt_parser)


# ------------------------------
#   DEFINE HELPERS
# ------------------------------

closest_match <- function(
  string,
  string_vector,
  max_dist = 3,
  match_start = 4) {
  # add coordinates for stops that have similar stop_id to existing one
  # (matching 1st four letters and edit dist < 3)
  if (match_start > 0) {
    ind <- sapply(string_vector, startsWith, substr(string, 0, match_start))
    string_vector <- string_vector[ind]
    }
  string_vector[amatch(string, string_vector, maxDist = max_dist)]
}

closest_transfer_lookup <- function(trans, existing_stops) {
  # add coordinates for stops that are in short transfer distance to known one
  trans2 <- trans %>% mutate(swap = from_stop_id,
                             from_stop_id = to_stop_id,
                             to_stop_id =  swap)
  lookup <- bind_rows(trans, trans2) %>%
    filter(to_stop_id %in% existing_stops,
           !(from_stop_id %in% existing_stops))  %>%
    group_by(from_stop_id) %>%
    arrange(min_transfer_time) %>%
    slice(1) %>%
    ungroup() %>%
    mutate(new_stop_id = from_stop_id,
           stop_id = to_stop_id) %>%
    select("new_stop_id", "stop_id")

  lookup
}

add_missing_stops <- function(gtfs) {
  transfer_close_stops <- closest_transfer_lookup(gtfs$transfers,
                                                  gtfs$stops$stop_id)  %>%
    left_join(gtfs$stops) %>%
    mutate(stop_id = new_stop_id) %>%
    select(-new_stop_id)
  gtfs$stops = bind_rows(gtfs$stops, transfer_close_stops)
  print(paste("Adding", nrow(transfer_close_stops),
              "stops based on transfers.txt"))

  existing_stops <- c(gtfs$stops$stop_id)
  other_files_stops <- unique(c(gtfs$stop_times$stop_id,
                                gtfs$transfers$from_stop_id,
                                gtfs$transfers$to_stop_id))
  still_missing_stops <- setdiff(other_files_stops, existing_stops)

  string_close_stops <- data.frame(new_stop_id = still_missing_stops) %>%
    mutate(stop_id = sapply(new_stop_id, closest_match, existing_stops)) %>%
    filter(!is.na(stop_id)) %>%
    left_join(gtfs$stops) %>%
    mutate(stop_id = new_stop_id) %>%
    select(-new_stop_id)
  gtfs$stops = bind_rows(gtfs$stops, string_close_stops)
  print(paste("Adding", nrow(string_close_stops),
              "stops based on stop_id string similarity."))

  gtfs
}

remove_missing_stops <- function(gtfs) {
  # remove stops that don't have coordinates
  existing_stops <- gtfs$stops$stop_id
  gtfs$stop_times <- gtfs$stop_times %>% filter(stop_id %in% existing_stops)
  gtfs$transfers <- gtfs$transfers %>% filter(to_stop_id %in% existing_stops,
                                              from_stop_id %in% existing_stops)
  gtfs
}

report_id_incidence <- function(id_name){
  inc <- sapply(names(gtfs), function(x) {
    if (id_name %in% names(gtfs[[x]])) unique(gtfs[[x]][[id_name]]) else c()})
  all_vals <- length(unique(unlist(inc)))
  c(sapply(inc, length), "all_vals"=all_vals)
}

id_list <- c("stop_id", "trip_id", "route_id", "service_id", "agency_id")


# ------------------------------
#   RUN CONVERSION
# ------------------------------

print("Converting ATOC to GTFS")
path_in <- opt$file

# Convert file to GTFS format
# number of cores can be altered. Potentially change to detectCores()-1.
gtfs <- atoc2gtfs(path_in = path_in, ncores = detectCores() - 1)
id_check <- id_list %>% sapply(report_id_incidence)
print(id_check)

# on the rail data we are missing one stop_id from stop list, remove:
if (id_check["stops", "stop_id"] < id_check["all_vals", "stop_id"]) {
  gtfs <- remove_missing_stops(gtfs)
}

# we can delete transfers as it is not needed
# (but has been fixed by the remove_missing stops already)
gtfs$transfers <- NULL

# Write out app-ready data to OTP folder
print("Saving results")
gtfs_write(gtfs,
           folder = "./data/processed",
           name = paste0("UK_rail", ".gtfs"))
