package catalog

import (
	"encoding/json"
	"fmt"
	"os"
	"sync"
)

type VideoItem struct {
	ItemID          string   `json:"item_id"`
	Title           string   `json:"title"`
	Category        string   `json:"category"`
	DurationSeconds int      `json:"duration_seconds"`
	Tags            []string `json:"tags"`
	AuthorID        string   `json:"author_id"`
	UploadDate      string   `json:"upload_date"`
	WatchRatioAvg   float64  `json:"watch_ratio_avg"`
	TotalViews      int      `json:"total_views"`
}

type Repository struct {
	mu    sync.RWMutex
	items map[string]VideoItem
	list  []VideoItem
}

func NewRepository(filePath string) (*Repository, error) {
	bytes, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read catalog file %s: %w", filePath, err)
	}

	var items []VideoItem
	if err := json.Unmarshal(bytes, &items); err != nil {
		return nil, fmt.Errorf("failed to parse catalog json: %w", err)
	}

	repo := &Repository{
		items: make(map[string]VideoItem, len(items)),
		list:  items,
	}

	for _, it := range items {
		repo.items[it.ItemID] = it
	}

	return repo, nil
}

func (r *Repository) Get(itemID string) (VideoItem, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	item, ok := r.items[itemID]
	return item, ok
}

func (r *Repository) ListAll() []VideoItem {
	r.mu.RLock()
	defer r.mu.RUnlock()
	copied := make([]VideoItem, len(r.list))
	copy(copied, r.list)
	return copied
}

func (r *Repository) Count() int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.items)
}
