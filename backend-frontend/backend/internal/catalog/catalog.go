// Package catalog loads the official KuaiRec item metadata exported for serving.
package catalog

import (
	"encoding/json"
	"fmt"
	"os"
)

// VideoItem holds official catalog metadata only. Fields that the release does
// not provide for an item are left empty (or null) rather than invented.
type VideoItem struct {
	ItemID                 string   `json:"item_id"`
	Title                  string   `json:"title"`
	HasCaption             bool     `json:"has_caption"`
	Category               string   `json:"category"`
	Categories             []string `json:"categories"`
	Tags                   []string `json:"tags"`
	AuthorID               string   `json:"author_id"`
	UploadDate             string   `json:"upload_date"`
	VideoType              string   `json:"video_type"`
	DurationSeconds        *float64 `json:"duration_seconds"`
	PositiveTrainingEvents int      `json:"positive_training_events"`
}

// Repository is an immutable, in-memory index of the catalog. It is safe for
// concurrent reads because it is never mutated after construction.
type Repository struct {
	items map[string]VideoItem
	order []string
}

// NewRepository reads a JSON array of VideoItem records.
func NewRepository(filePath string) (*Repository, error) {
	raw, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("read catalog %s: %w", filePath, err)
	}
	var items []VideoItem
	if err := json.Unmarshal(raw, &items); err != nil {
		return nil, fmt.Errorf("parse catalog: %w", err)
	}
	return FromItems(items)
}

// FromItems builds a repository and rejects empty or duplicate IDs.
func FromItems(items []VideoItem) (*Repository, error) {
	repo := &Repository{items: make(map[string]VideoItem, len(items)), order: make([]string, 0, len(items))}
	for _, item := range items {
		if item.ItemID == "" {
			return nil, fmt.Errorf("catalog item with empty item_id")
		}
		if _, dup := repo.items[item.ItemID]; dup {
			return nil, fmt.Errorf("duplicate catalog item_id %q", item.ItemID)
		}
		if item.Categories == nil {
			item.Categories = []string{}
		}
		if item.Tags == nil {
			item.Tags = []string{}
		}
		repo.items[item.ItemID] = item
		repo.order = append(repo.order, item.ItemID)
	}
	return repo, nil
}

// Get returns a copy of the item metadata.
func (r *Repository) Get(itemID string) (VideoItem, bool) {
	item, ok := r.items[itemID]
	return item, ok
}

// Has reports whether the item exists in the eligible catalog.
func (r *Repository) Has(itemID string) bool {
	_, ok := r.items[itemID]
	return ok
}

// Count returns the number of catalog items.
func (r *Repository) Count() int { return len(r.items) }
