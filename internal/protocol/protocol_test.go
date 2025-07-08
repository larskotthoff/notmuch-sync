package protocol

import (
	"bytes"
	"testing"
)

func TestDigest(t *testing.T) {
	// Test basic digest
	data := []byte("Hello, World!")
	digest := Digest(data)
	expected := "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
	if digest != expected {
		t.Errorf("Expected digest %s, got %s", expected, digest)
	}
	
	// Test with X-TUID line
	dataWithTUID := []byte("Subject: Test\nX-TUID: 123456789\nBody: Hello")
	digestWithTUID := Digest(dataWithTUID)
	
	// Should be the same as without X-TUID
	dataWithoutTUID := []byte("Subject: Test\nBody: Hello")
	digestWithoutTUID := Digest(dataWithoutTUID)
	
	if digestWithTUID != digestWithoutTUID {
		t.Errorf("Digest with X-TUID (%s) should equal digest without X-TUID (%s)", digestWithTUID, digestWithoutTUID)
	}
}

func TestProtocolReadWrite(t *testing.T) {
	// Reset global transfer counter
	GlobalTransfer = &Transfer{}
	
	// Test data
	testData := []byte("Hello, Protocol!")
	
	// Write to buffer
	var buf bytes.Buffer
	if err := Write(testData, &buf); err != nil {
		t.Fatalf("Failed to write data: %v", err)
	}
	
	// Read from buffer
	readData, err := Read(&buf)
	if err != nil {
		t.Fatalf("Failed to read data: %v", err)
	}
	
	// Compare
	if !bytes.Equal(testData, readData) {
		t.Errorf("Read data doesn't match written data. Expected %s, got %s", testData, readData)
	}
	
	// Check transfer counts
	expectedTransfer := int64(4 + len(testData)) // 4 bytes for length + data
	if GlobalTransfer.Read != expectedTransfer {
		t.Errorf("Expected read transfer %d, got %d", expectedTransfer, GlobalTransfer.Read)
	}
	if GlobalTransfer.Write != expectedTransfer {
		t.Errorf("Expected write transfer %d, got %d", expectedTransfer, GlobalTransfer.Write)
	}
}

func TestProtocolUint32(t *testing.T) {
	// Reset global transfer counter
	GlobalTransfer = &Transfer{}
	
	// Test value
	testValue := uint32(0x12345678)
	
	// Write to buffer
	var buf bytes.Buffer
	if err := WriteUint32(testValue, &buf); err != nil {
		t.Fatalf("Failed to write uint32: %v", err)
	}
	
	// Read from buffer
	readValue, err := ReadUint32(&buf)
	if err != nil {
		t.Fatalf("Failed to read uint32: %v", err)
	}
	
	// Compare
	if testValue != readValue {
		t.Errorf("Read uint32 doesn't match written value. Expected %d, got %d", testValue, readValue)
	}
	
	// Check transfer counts
	expectedTransfer := int64(4)
	if GlobalTransfer.Read != expectedTransfer {
		t.Errorf("Expected read transfer %d, got %d", expectedTransfer, GlobalTransfer.Read)
	}
	if GlobalTransfer.Write != expectedTransfer {
		t.Errorf("Expected write transfer %d, got %d", expectedTransfer, GlobalTransfer.Write)
	}
}