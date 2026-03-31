package main

import "sync"

type UserStats struct {
	TotalStreams      int
	SuccessfulStreams int
	FailedStreams     int
	TotalDurationSec  float64
}

type Database struct {
	mu         sync.Mutex
	users      map[int64]string
	stats      map[int64]UserStats
	broadcasts int
}

func newDB(_ string) *Database {
	return &Database{users: map[int64]string{}, stats: map[int64]UserStats{}}
}

func (d *Database) addUser(userID int64, username string) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.users[userID] = username
}

func (d *Database) addStreamStat(userID int64, duration float64, ok bool) {
	d.mu.Lock()
	defer d.mu.Unlock()
	s := d.stats[userID]
	s.TotalStreams++
	s.TotalDurationSec += duration
	if ok {
		s.SuccessfulStreams++
	} else {
		s.FailedStreams++
	}
	d.stats[userID] = s
}

func (d *Database) getUserStats(userID int64) UserStats {
	d.mu.Lock()
	defer d.mu.Unlock()
	return d.stats[userID]
}

func (d *Database) getAllUsers() []int64 {
	d.mu.Lock()
	defer d.mu.Unlock()
	ids := make([]int64, 0, len(d.users))
	for id := range d.users {
		ids = append(ids, id)
	}
	return ids
}

func (d *Database) addBroadcast() {
	d.mu.Lock()
	d.broadcasts++
	d.mu.Unlock()
}
