package protocol

import (
	"encoding/binary"
	"fmt"
	"io"
)

// Transfer tracks bytes read and written
type Transfer struct {
	Read  int64
	Write int64
}

// GlobalTransfer tracks global transfer statistics
var GlobalTransfer = &Transfer{}

// WriteUint32 writes a uint32 value in big-endian format
func WriteUint32(value uint32, stream io.Writer) error {
	if err := binary.Write(stream, binary.BigEndian, value); err != nil {
		return fmt.Errorf("failed to write uint32: %w", err)
	}
	GlobalTransfer.Write += 4
	return nil
}

// ReadUint32 reads a uint32 value in big-endian format
func ReadUint32(stream io.Reader) (uint32, error) {
	var value uint32
	if err := binary.Read(stream, binary.BigEndian, &value); err != nil {
		return 0, fmt.Errorf("failed to read uint32: %w", err)
	}
	GlobalTransfer.Read += 4
	return value, nil
}

// Write writes data to a stream with a 4-byte length prefix
func Write(data []byte, stream io.Writer) error {
	// Write 4-byte length prefix in big-endian format
	length := uint32(len(data))
	if err := binary.Write(stream, binary.BigEndian, length); err != nil {
		return fmt.Errorf("failed to write length prefix: %w", err)
	}
	GlobalTransfer.Write += 4

	// Write the data
	n, err := stream.Write(data)
	if err != nil {
		return fmt.Errorf("failed to write data: %w", err)
	}
	if n != len(data) {
		return fmt.Errorf("partial write: wrote %d bytes, expected %d", n, len(data))
	}
	GlobalTransfer.Write += int64(len(data))

	// Flush if the stream supports it
	if flusher, ok := stream.(interface{ Flush() error }); ok {
		if err := flusher.Flush(); err != nil {
			return fmt.Errorf("failed to flush: %w", err)
		}
	}

	return nil
}

// Read reads 4-byte length-prefixed data from a stream
func Read(stream io.Reader) ([]byte, error) {
	// Read 4-byte length prefix
	var length uint32
	if err := binary.Read(stream, binary.BigEndian, &length); err != nil {
		return nil, fmt.Errorf("failed to read length prefix: %w", err)
	}
	GlobalTransfer.Read += 4

	// Read the data
	data := make([]byte, length)
	n, err := io.ReadFull(stream, data)
	if err != nil {
		return nil, fmt.Errorf("failed to read data: %w", err)
	}
	if n != int(length) {
		return nil, fmt.Errorf("partial read: read %d bytes, expected %d", n, length)
	}
	GlobalTransfer.Read += int64(length)

	return data, nil
}