package main

import (
	"log"
	"os"

	"github.com/larskotthoff/notmuch-sync/internal/sync"
)

func main() {
	if err := sync.Run(os.Args[1:]); err != nil {
		log.Fatal(err)
	}
}