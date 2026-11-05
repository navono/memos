package v1

import (
	"testing"

	"github.com/stretchr/testify/require"

	storepb "github.com/usememos/memos/proto/gen/store"
	"github.com/usememos/memos/store"
)

func TestConvertAttachmentDoesNotExposeS3PresignedURL(t *testing.T) {
	attachment := &store.Attachment{
		UID:         "s3-test",
		Filename:    "test.jpg",
		Type:        "image/jpeg",
		Size:        1,
		StorageType: storepb.AttachmentStorageType_S3,
		Reference:   "http://172.17.0.1:9000/memos/test.jpg?X-Amz-Signature=x",
	}
	message := convertAttachmentFromStore(attachment)
	require.Empty(t, message.ExternalLink)
}

func TestConvertAttachmentKeepsExternalLink(t *testing.T) {
	attachment := &store.Attachment{
		UID:         "external-test",
		Filename:    "test.jpg",
		Type:        "image/jpeg",
		Size:        1,
		StorageType: storepb.AttachmentStorageType_EXTERNAL,
		Reference:   "https://example.com/test.jpg",
	}
	message := convertAttachmentFromStore(attachment)
	require.Equal(t, "https://example.com/test.jpg", message.ExternalLink)
}
