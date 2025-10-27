# Analysis of UNHCR data
# This file loads and prepares data for the Shiny app

# Set up ------------------------------------------------------------------
library(tidyverse)
library(plotly)
library(countrycode)

# Load data and shapefile
all_data <- read.csv("data/population.csv", skip = 14) %>% 
    filter(Year == max(Year, na.rm = T)) %>% 
    select(contains("Country"), Asylum.seekers)
shapefile <- map_data("world")

# List of iso3 codes
country_df <- all_data %>% 
    distinct(Country.of.asylum..ISO., Country.of.asylum)

choices <- setNames(country_df$Country.of.asylum..ISO., country_df$Country.of.asylum)
# Simple exploration
dim(all_data)
unique(all_data$Year)
length(unique(all_data$Country.of.origin))
length(unique(all_data$Country.of.asylum))

data <- all_data %>% 
  filter(Year == 2020) %>% 
  select(contains("Country"), Asylum.seekers)
dim(data)

country_of_interest <- "ESP"
country_name <- countrycode(country_of_interest, origin = 'iso3c', destination = 'country.name')
  
country_data <- data %>% 
  filter(Country.of.asylum..ISO. == country_of_interest)





# Make a map --------------------------------------------------------------



# Get iso3 codes and join on our data
