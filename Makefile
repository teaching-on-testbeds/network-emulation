SOURCES := network_emulation.md
NBS := $(SOURCES:.md=.ipynb)

%.ipynb: %.md
	pandoc --embed-resources --standalone --wrap=none  $< -o $@

all: $(NBS)

clean: 
	rm -f $(NBS)